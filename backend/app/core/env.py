from __future__ import annotations

import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _set_env_from_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped_line = line.strip()
        if (
            not stripped_line
            or stripped_line.startswith("#")
            or "=" not in stripped_line
        ):
            continue

        key, value = stripped_line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


try:
    from dotenv import load_dotenv as _load_dotenv
except ModuleNotFoundError:

    def load_environment() -> None:
        _set_env_from_file(BACKEND_ROOT / ".env")

else:

    def load_environment() -> None:
        _load_dotenv(dotenv_path=BACKEND_ROOT / ".env")
