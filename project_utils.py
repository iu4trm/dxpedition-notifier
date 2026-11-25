import json
import os
import tempfile
import time
from typing import Callable, TypeVar

import requests

T = TypeVar("T")


def load_dotenv(dotenv_path: str) -> None:
    """Load KEY=VALUE lines without overriding process environment variables."""
    if not os.path.exists(dotenv_path):
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError as err:
        print(f"Warning: could not read .env ({err})")


def atomic_json_dump(payload, path: str, *, ensure_ascii: bool = False) -> None:
    """Write JSON through a temporary file and atomically replace the destination."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=ensure_ascii)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def request_with_retry(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    retry_on: tuple[type[BaseException], ...] = (requests.RequestException,),
) -> T:
    """Run an HTTP operation with bounded exponential backoff."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    last_error: BaseException | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except retry_on as err:
            last_error = err
            if attempt == attempts - 1:
                break
            time.sleep(min(1.0 * (2**attempt), 4.0))

    if last_error is not None:
        raise last_error
    raise RuntimeError("request_with_retry ended without a result")
