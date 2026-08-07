"""Общие утилиты: безопасные имена файлов и каталогов."""
import re
from pathlib import PurePosixPath

INVALID_CHARS_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
TRAILING_DOTS_SPACES_RE = re.compile(r"[. ]+$")
RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_filename(name: str, *, allow_dir: bool = False) -> str:
    """Очищает имя от символов, несовместимых с ФС.

    Не допускает пути через ../ и абсолютные пути. Возвращает только имя
    (базовое), если allow_dir=False — применяется к каждому компоненту.
    """
    name = name.strip()
    if name in ("", ".", ".."):
        return "_"
    if name.startswith("/"):
        raise ValueError(f"Unsafe absolute path: {name!r}")
    parts = name.split("/")
    if any(p.strip() == ".." for p in parts):
        raise ValueError(f"Unsafe filename: {name!r}")
    parts = [INVALID_CHARS_RE.sub("_", p).strip() for p in parts]
    parts = [TRAILING_DOTS_SPACES_RE.sub("", p) or "_" for p in parts]
    parts = ["_" if p.upper() in RESERVED else p for p in parts]
    if not allow_dir:
        parts = [parts[-1]]
    result = "/".join(parts)
    if result.startswith("/") or ".." in PurePosixPath(result).parts:
        raise ValueError(f"Unsafe filename: {name!r}")
    return result


def sanitize_component(name: str) -> str:
    return sanitize_filename(name, allow_dir=False)


def unique_path(base: str, name: str, suffix: str = "", *, id_suffix: str | None = None) -> str:
    """Формирует уникальный путь к каталогу.

    Если каталог с именем `name` уже существует, добавляет `[id-N]`.
    Возвращает имя каталога (не полный путь).
    """
    candidate = sanitize_component(name)
    if id_suffix:
        candidate = f"{candidate} [id-{id_suffix}]"
    return candidate


def ensure_safe_relative_path(path: str) -> str:
    """Проверяет, что относительный путь не выходит за пределы каталога."""
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"Unsafe relative path: {path!r}")
    return path