import ast
import logging
import re
import time

import click
from wikibaseintegrator import wbi_helpers
from wikibaseintegrator.datatypes import ExternalID, Item, MonolingualText, String, URL
from wikibaseintegrator.models import Qualifiers
from wikibaseintegrator.wbi_enums import ActionIfExists


DATATYPES = {"Item": Item, "URL": URL, "ExternalID": ExternalID,
             "String": String, "MonolingualText": MonolingualText}


def entityId(value, created_entities):
    value = created_entities.get(value, value)
    if not isinstance(value, str) or not re.fullmatch(r"Q[1-9][0-9]*", value):
        raise ValueError(f"Unresolved entity: {value}")
    return value


def makeClaim(data, created_entities):
    datatype = data["datatype"]
    if datatype not in DATATYPES:
        raise ValueError(f"Unsupported datatype: {datatype}")
    if not re.fullmatch(r"P[1-9][0-9]*", data["p"]):
        raise ValueError(f"Invalid property: {data['p']}")
    value = data["o"]
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Statement value must be a nonempty string")
    if datatype == "Item":
        value = entityId(value, created_entities)
    qualifiers = Qualifiers()
    if data.get("qualifiers") is not None and not isinstance(data["qualifiers"], list):
        raise ValueError("Qualifiers must be a list of [item, property] pairs or None")
    for qualifier in data.get("qualifiers") or []:
        if not isinstance(qualifier, dict):
            qualifier_value, prop = qualifier
            qualifier = {"datatype": "Item", "p": prop, "o": qualifier_value}
        qualifiers.add(makeClaim(qualifier, created_entities))
    if datatype == "MonolingualText":
        language = data["language"]
        if not isinstance(language, str) or not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]+)*", language):
            raise ValueError("MonolingualText requires a language code")
        return MonolingualText(text=value, language=language, prop_nr=data["p"], qualifiers=qualifiers)
    return DATATYPES[datatype](value=value, prop_nr=data["p"], qualifiers=qualifiers)


def entityReferences(data):
    if data.get("datatype") == "Item":
        yield data["o"]
    for qualifier in data.get("qualifiers") or []:
        if isinstance(qualifier, dict):
            yield from entityReferences(qualifier)
        else:
            yield qualifier[0]


def parseOperations(lines):
    operations, created_entities = [], {}
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            operation = ast.literal_eval(line)
            if not isinstance(operation, (list, tuple)) or len(operation) != 2 or not isinstance(operation[1], dict):
                raise ValueError("Expected [operation, fields]")
            kind, data = operation
            if kind == "create":
                for field in ("LABEL", "DESCRIPTION"):
                    if not isinstance(data[field], str) or not data[field].strip() or len(data[field]) > 250:
                        raise ValueError(f"{field} must contain 1 to 250 characters")
                if data["LABEL"] in created_entities:
                    raise ValueError(f"Duplicate creation label: {data['LABEL']}")
                created_entities[data["LABEL"]] = f"Q{900000000 + len(created_entities)}"
            elif kind == "statement":
                entityId(data["s"], created_entities)
                makeClaim(data, created_entities)
            elif kind == "remove_statement":
                subject = entityId(data["s"], {})
                pattern = re.escape(subject) + r"\$[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
                if not re.fullmatch(pattern, data["id"]):
                    raise ValueError("Statement GUID must belong to the specified subject")
            else:
                raise ValueError(f"Unsupported operation: {kind}")
            operations.append(operation)
        except (ValueError, TypeError, KeyError, SyntaxError) as error:
            raise click.ClickException(f"Invalid operation at line {number}: {type(error).__name__}: {error}") from error
    return operations


def runRequest(action, target, request, **kwargs):
    """Annotate WBI's existing waits without changing its retry policy."""
    logger = logging.getLogger(wbi_helpers.__name__)
    start, retries = time.monotonic(), 0

    def context(record):
        nonlocal retries
        message = record.getMessage()
        if "sleep" in message.lower():
            retries += 1
            record.msg = (f"[WAIT {action} {target}] retry={retries} "
                          f"elapsed={time.monotonic() - start:.1f}s | {message}")
            record.args = ()
        return True

    click.echo(f"[{action}] {target}")
    logger.addFilter(context)
    try:
        return request(**kwargs)
    finally:
        logger.removeFilter(context)


def createEmptyEntity(data, wbi):
    item = wbi.item.new()
    item.labels.set(language="en", value=data["LABEL"])
    item.descriptions.set(language="en", value=data["DESCRIPTION"])
    item = runRequest("CREATE", data["LABEL"], item.write, summary="created " + data["LABEL"])
    click.echo(f"Entity saved: {item.id} (created {data['LABEL']})")
    return item


def updateChanges(operation_list, wbi):
    created_entities, subject_map, failed_creations, errors = {}, {}, set(), []
    created_count = saved_count = 0

    def failed(message):
        errors.append(message)
        click.echo(message, err=True)

    for number, (kind, data) in enumerate(operation_list, 1):
        target = data.get("LABEL", data.get("s", "unknown"))
        context = f"operation {number} {kind} {target} {data.get('p', data.get('id', ''))}"
        dependencies = [data.get("s")]
        if kind == "statement":
            dependencies.extend(entityReferences(data))
        if failed_creations.intersection(dependencies):
            failed(f"PENDING {context}: dependent entity creation failed")
            continue
        try:
            if kind == "create":
                item = createEmptyEntity(data, wbi)
                created_entities[data["LABEL"]] = item.id
                subject_map[item.id] = [item, []]
                created_count += 1
                continue
            subject = entityId(data["s"], created_entities)
            if subject not in subject_map:
                item = runRequest("LOAD", subject, wbi.item.get, entity_id=subject)
                subject_map[subject] = [item, []]
            item, pending = subject_map[subject]
            if kind == "remove_statement":
                claim = next((c for c in item.claims if c.id == data["id"] and not c.removed), None)
                if claim is None:
                    click.echo(f"Already absent: {data['id']}")
                    continue
                claim.remove()
            elif kind == "statement":
                item.claims.add(makeClaim(data, created_entities), action_if_exists=ActionIfExists.FORCE_APPEND)
            else:
                raise ValueError(f"Unsupported operation: {kind}")
            pending.append(context)
            click.echo(f"Statement prepared: {kind} {subject} {data.get('p', data.get('id', ''))}")
        except Exception as error:
            if kind == "create":
                failed_creations.add(data["LABEL"])
            failed(f"ERROR {context}: {type(error).__name__}: {error}")

    for subject, (item, pending) in subject_map.items():
        if not pending:
            continue
        try:
            runRequest("SAVE", subject, item.write, summary=f"SALTbot: {len(pending)} operations")
            saved_count += 1
            click.echo(f"Entity saved: {subject} | operations={len(pending)}")
        except Exception as error:
            for context in pending:
                failed(f"PENDING {context}: SAVE {subject}: {type(error).__name__}: {error}")
    click.echo(f"Update summary: created entities={created_count}; updated entities={saved_count}; failed/pending operations={len(errors)}")
    return errors


def executeOperations(operation_list, auto, wbi):
    click.echo("SALTbot WILL APPLY THESE OPERATIONS IN WIKIDATA")
    for kind, data in operation_list:
        click.echo(f"{kind}: {data}")
    if not auto and not click.confirm("CONFIRM", default=False):
        click.echo("Update cancelled; operation files preserved.")
        return
    errors = updateChanges(operation_list, wbi)
    if errors:
        raise click.ClickException(f"Update incomplete: {len(errors)} failed/pending operations; see errors above.")

