"""Клиент API «МояКоманда»: авторизация, категории, статьи, файлы."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests

from .config import Config
from .logging import logger

DEFAULT_TIMEOUT = 60


class MyTeamError(Exception):
    """Базовая ошибка клиента."""


class AuthError(MyTeamError):
    pass


class ApiError(MyTeamError):
    def __init__(self, message: str, status_code: int | None = None,
                 response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class MyTeamClient:
    def __init__(self, config: Config, session: requests.Session | None = None):
        self.config = config
        self.base_url = config.myteam_base_url
        self.session = session or requests.Session()
        self._token: str | None = None

    # -- auth -----------------------------------------------------------------
    def _headers(self, json: bool = True) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if json:
            headers["Content-Type"] = "application/json"
        return headers

    def authenticate(self) -> str:
        """Получает Bearer Token. Токен не сохраняется на диск."""
        payload = {
            "email": self.config.myteam_email,
            "password": self.config.myteam_password,
            "language": "ru",
            "remember": True,
        }
        token = self._try_login("/api/login-mobile", payload)
        if not token:
            token = self._try_login("/api/login", payload)
        if not token:
            raise AuthError("Login response does not contain data.token")
        self._token = token
        logger.info("Authentication successful")
        return token

    def _try_login(self, path: str, payload: dict) -> str | None:
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, json=payload, headers=self._headers(),
                                 timeout=DEFAULT_TIMEOUT)
        if resp.status_code >= 400:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        token = (data.get("data") or {}).get("token")
        return token or None

    # -- generic request ------------------------------------------------------
    def _get(self, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, headers=self._headers(), timeout=DEFAULT_TIMEOUT, **kwargs)
        if resp.status_code == 401:
            raise ApiError(f"Unauthorized for {path}", status_code=401)
        if resp.status_code >= 400:
            raise ApiError(f"GET {path} failed (HTTP {resp.status_code}): {resp.text[:300]}",
                           status_code=resp.status_code)
        try:
            return resp.json()
        except ValueError:
            return resp.text

    # -- knowledge base --------------------------------------------------------
    def get_groups(self) -> list[dict]:
        """Список категорий: [{id, name, articlesCount}]."""
        data = self._get("/api/knowledge-base/groups")
        return (data.get("data") or {}).get("groups") or []

    def get_group_articles(self, group_id: int, group_name: str = "") -> list[dict]:
        """Список статей категории с учётом пагинации (все страницы)."""
        articles: list[dict] = []
        page = 1
        while True:
            resp = self._get(f"/api/knowledge-base/groups/{group_id}",
                             params={"page": page})
            payload = resp.get("data") or {}
            batch = payload.get("articles") or []
            articles.extend(batch)

            pagination = payload.get("pagination")
            total_pages = _total_pages(pagination)
            if total_pages is not None and page >= total_pages:
                break
            if not batch:
                break
            if len(batch) < _per_page(pagination):
                break
            page += 1
            if page > 10000:  # защита от бесконечного цикла
                raise ApiError("Pagination exceeded safety limit")
        return articles

    def get_article(self, article_id: int) -> dict:
        """Детальная статья (v2), возвращает объект KnowledgeBaseItem."""
        data = self._get(f"/api/v2/knowledge-base/articles/{article_id}")
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    def get_tags(self) -> list[dict]:
        """Список тегов: [{id, name, color}]."""
        data = self._get("/api/knowledge-base/tags")
        return (data.get("data") or {}).get("tags") or []

    # -- files ----------------------------------------------------------------
    def download(self, url_or_path: str) -> bytes:
        """Скачивает файл по относительному пути или полному URL.

        Сначала пробуем прямой GET по абсолютному URL с Bearer-токеном
        (работает и для /storage/... медиа, и для download_path). Если не
        получается — используем /api/file/download?path=... в качестве fallback.
        Внешние URL не скачиваются.
        """
        abs_url = url_or_path.strip()
        if not abs_url.startswith(("http://", "https://")):
            abs_url = f"{self.base_url}{abs_url if abs_url.startswith('/') else '/' + abs_url}"
        if urlparse(abs_url).netloc != self._netloc():
            raise ApiError(f"Refusing to download external URL: {url_or_path}")
        try:
            return self._download_direct(abs_url)
        except Exception:  # noqa: BLE001
            path = self._to_storage_path(url_or_path)
            if path is None:
                raise
            return self._download_via_api(path)

    def _is_host(self, url: str) -> bool:
        return urlparse(url).netloc == self._netloc()

    def _to_storage_path(self, url_or_path: str) -> str | None:
        """Приводит src/path к аргументу `path` для /api/file/download.

        Контракт downloadFile: path типа 'public/images/avatar/x.jpg'.
        """
        url = url_or_path.strip()
        if url.startswith(("http://", "https://")):
            parsed = urlparse(url)
            if parsed.netloc and parsed.netloc != self._netloc():
                return None  # внешний URL
            url = parsed.path or ""
        url = url.split("?", 1)[0]
        url = url.lstrip("/")
        if url.startswith("storage/"):
            url = url[len("storage/"):]
        if not url:
            return None
        return url

    def _netloc(self) -> str:
        return urlparse(self.base_url).netloc

    def _download_via_api(self, path: str) -> bytes:
        resp = self.session.get(
            f"{self.base_url}/api/file/download",
            params={"path": path},
            headers=self._headers(json=False),
            timeout=DEFAULT_TIMEOUT,
            stream=True,
        )
        if resp.status_code >= 400:
            raise ApiError(f"Download {path} failed (HTTP {resp.status_code})",
                           status_code=resp.status_code)
        return b"".join(resp.iter_content(chunk_size=65536))

    def _download_direct(self, abs_url: str) -> bytes:
        resp = self.session.get(abs_url, headers=self._headers(json=False),
                                timeout=DEFAULT_TIMEOUT, stream=True)
        if resp.status_code >= 400:
            raise ApiError(f"Direct download {abs_url} failed (HTTP {resp.status_code})",
                           status_code=resp.status_code)
        return b"".join(resp.iter_content(chunk_size=65536))


def _total_pages(pagination: Any) -> int | None:
    if not isinstance(pagination, dict):
        return None
    return pagination.get("totalPages")


def _per_page(pagination: Any) -> int:
    if not isinstance(pagination, dict):
        return 15
    return int(pagination.get("perPage") or 15)


def is_internal_resource(url: str, base_url: str) -> bool:
    """True, если URL относится к внутреннему хранилищу «МояКоманда»."""
    from urllib.parse import urlparse

    if url.startswith("data:"):
        return False
    if not url.startswith(("http://", "https://")):
        return True  # относительный путь — внутренний
    parsed = urlparse(url)
    return parsed.netloc == urlparse(base_url).netloc or url.startswith("/")