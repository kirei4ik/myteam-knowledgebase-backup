"""Структурированное логирование в stdout/stderr с маскированием секретов."""
import sys


class Logger:
    def __init__(self) -> None:
        self._secrets: list[str] = []

    def configure(self, secrets: list[str]) -> None:
        self._secrets = [s for s in secrets if s]

    def _mask(self, message: str) -> str:
        for secret in self._secrets:
            if secret:
                message = message.replace(secret, "***")
        return message

    def info(self, message: str) -> None:
        print(f"[INFO] {self._mask(message)}", file=sys.stdout, flush=True)

    def warn(self, message: str) -> None:
        print(f"[WARN] {self._mask(message)}", file=sys.stderr, flush=True)

    def error(self, message: str) -> None:
        print(f"[ERROR] {self._mask(message)}", file=sys.stderr, flush=True)


logger = Logger()