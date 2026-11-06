#!/usr/bin/env sh

set -eu

SALTBOT_BIN="${SALTBOT_BIN:-saltbot}"
ENV_FILE="${SALTBOT_ENV_FILE:-}"

if [ -z "$ENV_FILE" ] && [ "$#" -gt 0 ] && [ -f "$1" ]; then
    ENV_FILE="$1"
    shift
fi

if [ -z "$ENV_FILE" ] && [ -f ".env" ]; then
    ENV_FILE=".env"
fi

if [ -n "$ENV_FILE" ]; then
    if [ ! -f "$ENV_FILE" ]; then
        echo "Missing env file: $ENV_FILE" >&2
        exit 1
    fi

    # Export all variables loaded from .env
    set -a
    . "$ENV_FILE"
    set +a
fi

# SALTBot configuration
SALT_USER="${WIKIBASE_USER:-}"
SALT_PASSWORD="${WIKIBASE_PASSWORD:-}"
GITHUB_API_TOKEN="${GITHUB_API_TOKEN:-}"
SALT_MEDIAWIKI_API_URL="${MEDIAWIKI_API_URL:-}"
SALT_SPARQL_ENDPOINT_URL="${SPARQL_ENDPOINT_URL:-}"
SALT_WIKIBASE_URL="${WIKIBASE_URL:-}"

if [ -z "$SALT_USER" ]; then
    echo "Missing WIKIBASE_USER" >&2
    exit 1
fi

if [ -z "$SALT_PASSWORD" ]; then
    echo "Missing WIKIBASE_PASSWORD" >&2
    exit 1
fi

printf '%s\n%s\n%s\n%s\n%s\n%s\n' \
    "$SALT_USER" \
    "$SALT_PASSWORD" \
    "$GITHUB_API_TOKEN" \
    "$SALT_MEDIAWIKI_API_URL" \
    "$SALT_SPARQL_ENDPOINT_URL" \
    "$SALT_WIKIBASE_URL" \
    | "$SALTBOT_BIN" configure

echo "SALTBot configuration created successfully."

if [ "$#" -gt 0 ]; then
    exec "$@"
fi
