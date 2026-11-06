import time, os, json, fcntl, tempfile, time, shutil

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .cruds import resqui_runner, resqui_report_generation
from .config import (
    BASE_DIR,
    QUEUE_NAME,
    TOKEN,
    RATE_LIMIT_QUEUE,
    RATE_LIMIT_RESQUI_ENABLED,
    RATE_LIMIT_WAIT_SECONDS,
    RETRYABLE_ERRORS,
    RESQUI_CONF,
    RESQUI_MAX_RETRIES,
    RESQUI_RETRY_DELAY_SECONDS,
)
from .rabbitmq import rabbit_connect
from .repository_state import build_resqui_repository_paths, promote_staged_resqui_results
from .safe_logging import sanitize_data, sanitize_text
MAX_RETRIES = RESQUI_MAX_RETRIES

## Auxiliares
def timestamp(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {sanitize_text(msg)}", flush=True)
    

def summarize_command_output(status: dict, max_chars: int = 1200) -> str:
    parts = []
    for field in ("stderr", "stdout"):
        value = sanitize_text(status.get(field) or "")
        if not isinstance(value, str):
            value = sanitize_text(value)

        value = value.strip()
        if value:
            parts.append(f"{field.upper()}:\n{value[-max_chars:]}")

    if not parts:
        parts.append(f"STATUS: {sanitize_data(status)}")

    return "\n".join(parts)


def write_repository_failed_assessment(
    active_dir: str | Path,
    response_status: dict,
    attempts: list[dict] | None = None,
) -> Path:
    active_path = Path(active_dir)
    active_path.mkdir(parents=True, exist_ok=True)

    failed_file = active_path / "failed_assessment.json"

    write_json_atomic(
        str(failed_file),
        {
            "detail": sanitize_data(response_status),
            "error_summary": summarize_command_output(response_status),
            "attempts": sanitize_data(attempts or []),
        },
    )

    return failed_file

# rutas del fichero de estado y del fichero lock compartido entre workers
def get_status_paths(target):
    target_dir = os.path.join(BASE_DIR, "outputs", "resqui", target)

    os.makedirs(target_dir, exist_ok=True)

    status_file = os.path.join(target_dir, "status.json")
    lock_file = os.path.join(target_dir, "status.lock")

    return status_file, lock_file


# bloqueo exclusivo para que solo un worker acceda al status a la vez
@contextmanager
def acquire_status_lock(target):
    status_file, lock_file = get_status_paths(target)

    # el lock debe estar en el volumen outputs compartido por todos los workers
    with open(lock_file, "a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)

        try:
            yield status_file
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


# escritura atomica para evitar que otro worker lea un json incompleto
def write_json_atomic(file_path, data):
    directory = os.path.dirname(file_path)

    file_descriptor, temporary_path = tempfile.mkstemp(
        prefix=".status_",
        suffix=".tmp",
        dir=directory,
    )

    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(data, temporary_file, indent=2)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, file_path)

    except Exception:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)

        raise


# incremento protegido del numero de repositorios procesados
def record_resqui_repository_result(target,repository_url,succeeded):
    with acquire_status_lock(target) as status_file:
        if not os.path.isfile(status_file):
            raise FileNotFoundError(
                f"Status file not initialized: {status_file}"
            )

        with open(status_file, "r", encoding="utf-8") as file:
            status_data = json.load(file)

        expected_repos = int(status_data["expected_repos"])
        processed_repos = min(
            int(status_data["processed_repos"]) + 1,
            expected_repos,
        )
        successful_repos = int(
            status_data.get("successful_repos", 0)
        )
        failed_repos = list(
            status_data.get("failed_repos", [])
        )

        if succeeded:
            successful_repos = min(
                successful_repos + 1,
                expected_repos,
            )
        elif repository_url not in failed_repos:
            failed_repos.append(repository_url)

        status_data["processed_repos"] = processed_repos
        status_data["successful_repos"] = successful_repos
        status_data["failed_repos"] = failed_repos

        if processed_repos < expected_repos:
            status_data["status"] = "processing"
        else:
            status_data["status"] = "completed"

        write_json_atomic(status_file, status_data)
        return status_data.copy()





def wait_for_token(channel):

    # esperamos a que haya token
    while True:
        method, properties, body = channel.basic_get(queue=RATE_LIMIT_QUEUE)

        if method:
            channel.basic_ack(method.delivery_tag)
            return

        time.sleep(RATE_LIMIT_WAIT_SECONDS)

            
            
#llamada a resqui_runner y cambios de estado de la bbdd
def resqui_indicators_generation(job_id, target, repo_url, base_dir, token, conf_path):    
    repository_paths = build_resqui_repository_paths(base_dir,target,repo_url)
    repository_paths.staging_root.mkdir(parents=True,exist_ok=True)

    succeeded = False
    last_status = {}
    attempts = []

    for attempt in range(MAX_RETRIES):
        staging_path = Path(
            tempfile.mkdtemp(prefix=f"{repository_paths.active_dir.name}-",
                            dir=repository_paths.staging_root)
            )

        try:
            response = resqui_runner(str(staging_path),repo_url,token)
            last_status = response.status
            attempts.append(
                {
                    "attempt": attempt + 1,
                    "status": last_status,
                    "summary": summarize_command_output(last_status),
                }
            )

            if last_status["status"] == "success":
                try:
                    summary_path = staging_path / "resqui_summary.json"
                    output_report_path = staging_path / "resqui_report.md"

                    resqui_report_generation(
                        input_path=summary_path,
                        conf_path=conf_path,
                        output_report_path=output_report_path,
                    )

                    promote_staged_resqui_results(
                        staging_path,
                        repository_paths.active_dir,
                    )
                                                
                except Exception as exc:
                    last_status = {
                        "status": "error",
                        "returncode": -1,
                        "stdout": "",
                        "stderr": str(exc)
                    }
                    attempts[-1] = {
                        "attempt": attempt + 1,
                        "status": last_status,
                        "summary": summarize_command_output(last_status),
                    }
                else:
                    succeeded = True
                    break

            error_text = str(last_status)
            retryable = any(error in error_text for error in RETRYABLE_ERRORS)

            if not retryable:
                break

            retry_number = attempt + 1

            if retry_number >= MAX_RETRIES:
                timestamp(
                    f"[{job_id}] max retries reached. "
                    f"Last error:\n{summarize_command_output(last_status)}"
                )
                break

            timestamp(
                f"[{job_id}] retry {retry_number}/{MAX_RETRIES} "
                f"due to network error. Last error:\n"
                f"{summarize_command_output(last_status)}"
            )
            time.sleep(RESQUI_RETRY_DELAY_SECONDS)

        finally:
            try:
                if staging_path.exists():
                    shutil.rmtree(staging_path)

                timestamp(
                    f"[{job_id}] Temporary directory cleaned: "
                    f"{staging_path}"
                )

            except OSError as exc:
                timestamp(
                    f"[{job_id}] ERROR cleaning temporary directory "
                    f"{staging_path}: {exc}"
                )

    if not succeeded:
        write_repository_failed_assessment(
            repository_paths.active_dir,
            last_status,
            attempts,
        )

    status_data = record_resqui_repository_result(target, repo_url, succeeded)

    timestamp(f"[RESQUI] {target} Progress: {status_data['processed_repos']}/{status_data['expected_repos']} repos processed")

    return succeeded
            
            

# carga del mensaje de la cola y envío a background
def process_message(ch, method, properties, body):
    job_id = "unknown"
    try:
        message = json.loads(body.decode())
        job_id = message["job_id"]
        repo_url = message["repo_url"]
        target = message["target"]

        start = time.time()
        timestamp(f"[{job_id}] Received job")

        if RATE_LIMIT_RESQUI_ENABLED:
            wait_for_token(ch)

        succeeded = resqui_indicators_generation(
            job_id,
            target,
            repo_url,
            BASE_DIR,
            TOKEN,
            RESQUI_CONF,
        )

        total_time = time.time() - start

        result = "completed" if succeeded else "failed"

        timestamp(f"[{job_id}] {result} in {total_time:.2f}s")

        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except Exception as e:
        timestamp(f"[{job_id}] Error processing job: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)







# establecimiento de conexion con cola y escucha
def worker():
    timestamp(f"** WORKER STARTED **\n\t\t using configuration {RESQUI_CONF}")
    
    # definicion de credenciales, la conexion, credenciales y apertura de canal
    connection = rabbit_connect()
    channel = connection.channel()


    # worker recibe 1 trabajo y recibe el siguiente al terminar
    channel.basic_qos(prefetch_count=1)
    
    # escuchar cola queue procesando por callback dado
    channel.basic_consume( queue=QUEUE_NAME, on_message_callback=process_message)
    
    timestamp("Waiting for jobs...")

    channel.start_consuming()
            
            
            
            
            
if __name__ == "__main__":
    worker()
