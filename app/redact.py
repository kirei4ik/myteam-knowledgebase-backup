"""Маскирование пар логин/пароль и прочих креденшиалов в выгружаемых данных."""
from __future__ import annotations

import re

PLACEHOLDER = "REDACTED"

# Ключевые слова, после которых ожидается секретное значение
KEYWORDS = (
    "логин", "пароль[уе]?", "пороль",
    "password", "passwd", "pass", "pwd",
    "login", "username", "account", "secret", "auth",
    "access[_-]?token", "api[_-]?key",
)

# «логин/пароль <значение>» с допустимыми маркерами разметки между словом и значением
VALUE_PATTERN = re.compile(
    r"(?i)"
    r"\b(?:"
    + "|".join(KEYWORDS)
    + r")\b"
    r"(?:<[^>]*>|\*\*|\*|`|:)*"          # маркеры HTML/bold между словом и значением
    r"\s*[:=]?\s*"
    r"(?:<[^>]*>|\*\*|\*|`)*"
    r"(?P<value>[^\s,;!?<>()[\]][^\s,;!?<>()]*)",
    re.UNICODE,
)

# email-ссылка вида  [user@host](mailto:user@host)  — маскируем целиком
MAILTO_PATTERN = re.compile(r"\[[^\[\]]+@[^\[\]]+\]\(mailto:[^)\s]+\)")

# HTML-ссылка mailto:<email>  — маскируем адрес независимо от вложенности тегов
HTML_MAILTO_PATTERN = re.compile(
    r'(?i)(mailto:)[^"\'>\s@]+@[^"\'>\s]+',
    re.UNICODE,
)

# видимый текст mailto-ссылки  <a href="mailto:...">user@host</a>
HTML_MAILTO_TEXT_PATTERN = re.compile(
    r'(?i)(<a[^>]*href=["\']mailto:[^"\']+["\'][^>]*>)[^<]*@[^<]*',
    re.UNICODE,
)

# значения-«инструкции», а не секреты
STOPWORDS = {
    "для", "пример", "свой", "на", "по", "это", "или", "и", "ваш",
    "стандартный", "новый", "системный", "аккаунт", "используйте",
    "использовать", "входа", "вход", "доступа", "создать", "сохранить",
    "ключ", "пароль", "доступ", "подключения",
}

_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _need_secret(value: str) -> bool:
    """Значение считается секретом, если содержит цифру или @ (email).

    Чисто буквенное «слово-инструкция» (например 'Используйте ваш
    стандартный логин') секретом не считается.
    """
    low = value.strip("*`:[]()'\"").strip()
    if not low:
        return False
    if low.lower() in STOPWORDS:
        return False
    if re.fullmatch(r"[а-яёa-z]+", low, re.IGNORECASE):
        return False
    return bool(re.search(r"[\d@]", low))


def _redact_value_match(m: re.Match) -> str:
    raw = m.group("value")
    value = raw.strip("`*")
    if not _need_secret(value):
        return m.group(0)
    start, end = m.start("value"), m.end("value")
    inner_start = len(raw) - len(raw.lstrip("`*"))
    inner_end = len(raw.rstrip("`*"))
    masked = raw[:inner_start] + PLACEHOLDER + raw[inner_end:]
    return m.group(0)[:start - m.start()] + masked + m.group(0)[end - m.start():]


def redact_credentials(text: str) -> str:
    """Заменяет найденные креденсы на placeholder. Идемпотентно."""
    if not text:
        return text
    out = MAILTO_PATTERN.sub(lambda m: "[REDACTED](mailto:********)", text)
    out = HTML_MAILTO_PATTERN.sub(lambda m: m.group(1) + "********", out)
    out = HTML_MAILTO_TEXT_PATTERN.sub(lambda m: m.group(1) + "REDACTED", out)
    return VALUE_PATTERN.sub(_redact_value_match, out)


def redact_object(obj, key_names: frozenset[str] | None = None) -> None:
    """Рекурсивно маскирует строковые значения объекта (dict/list).

    Если key_names задан — только значения по этим ключам (например
    'content'); иначе — все строки.
    """
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(v, str) and (key_names is None or k in key_names):
                obj[k] = redact_credentials(v)
            elif isinstance(v, (dict, list)):
                redact_object(v, key_names=key_names)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str) and key_names is None:
                obj[i] = redact_credentials(v)
            elif isinstance(v, (dict, list)):
                redact_object(v, key_names=key_names)