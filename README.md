# myteam-kb-backup

Автономный модуль резервного копирования базы знаний сервиса «МояКоманда» через REST API.

Backup — это человекочитаемая структура каталогов, которую можно открыть обычным файловым менеджером или как Obsidian Vault:

```
knowledge-base/
└── ИТ - инструменты/
    └── Настройка подключения/
        ├── Настройка подключения.md
        ├── image-1.png
        ├── .source.html
        └── .metadata.json
```

## Логическая модель

- категория → папка;
- статья → отдельная папка;
- текст статьи → Markdown-файл с YAML front matter;
- картинки и вложения → локальные файлы рядом со статьёй;
- ссылки в Markdown — относительные.

## Возможности

- авторизация через `POST /api/login-mobile` (fallback на `/api/login`), Bearer-токен получается при каждом запуске и на диск не пишется;
- полный список категорий и статей с учётом пагинации;
- HTML → Markdown (`markdownify` + `BeautifulSoup`);
- скачивание картинок/видео/вложений с заменой ссылок на локальные;
- сохранение `.source.html` и `.metadata.json`;
- `manifest.json` со счётчиками и SHA-256 файлов;
- storage backends: `local`, `github`, `s3`;
- snapshots (`latest/` + `snapshots/<timestamp>/knowledge-base.zip`) с retention и минимальным интервалом;
- параллельная обработка статей и ретраи сетевых запросов;
- маскирование логинов/паролей и email в выгружаемых файлах (`REDACT`);
- `--dry-run` и `--output`.

## Quick Start

```bash
cp .env.example .env   # заполните MYTEAM_EMAIL / MYTEAM_PASSWORD
```

В `.env`:

```env
MYTEAM_BASE_URL=https://your-team.ismyteam.ru
MYTEAM_EMAIL=you@company.ru
MYTEAM_PASSWORD=secret
STORAGE_BACKEND=local
LOCAL_BACKUP_DIR=./backups
```

Запуск:

```bash
python backup.py
```

Результат:

```text
project/
├── backup.py
└── backups/
    ├── latest/
    │   └── knowledge-base/
    └── snapshots/
        └── <timestamp>/
            └── knowledge-base.zip
```

### Dry-run

```bash
python backup.py --dry-run
```

Строит полный backup в `WORK_DIR`, ничего не публикует. Удобно для проверки до первого реального прогона.

### Локальная разработка

```bash
python backup.py --output ./test-backup
```

`--output` переопределяет `LOCAL_BACKUP_DIR`.

## Docker

```bash
docker build -t myteam-kb-backup .
```

```bash
docker run --rm \
  --env-file .env \
  -v "$(pwd)/backups:/data/backups" \
  -e LOCAL_BACKUP_DIR=/data/backups \
  myteam-kb-backup
```

В `docker-compose`/Coolify обязательно подключается persistent volume `/data/backups`.

## GitHub backend

```env
STORAGE_BACKEND=github
GITHUB_TOKEN=
GITHUB_REPOSITORY=organization/repository
GITHUB_BRANCH=main
GITHUB_BACKUP_PATH=knowledge-base
GITHUB_COMMIT_AUTHOR_NAME=MyTeam Backup
GITHUB_COMMIT_AUTHOR_EMAIL=
```

Backend выполняет `git clone` → замену содержимого `GITHUB_BACKUP_PATH` → `commit` → `push`. При отсутствии изменений новый commit не создаётся. Требуется установленный `git` в окружении.

## S3 backend

```env
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_BUCKET=
S3_REGION=
S3_PREFIX=myteam-kb
S3_VERIFY_SSL=true
```

Поддерживается любой S3-compatible storage (AWS, MinIO, DO Spaces и т.п.). В bucket создаётся:

```text
myteam-kb/
├── latest/
│   └── knowledge-base/
└── snapshots/
    └── <timestamp>/
        └── knowledge-base.zip
```

## Snapshots и retention

```env
CREATE_SNAPSHOT=true
SNAPSHOT_FORMAT=zip
SNAPSHOT_RETENTION_DAYS=30      # хранить не старше N дней
SNAPSHOT_RETENTION_COUNT=7      # держать максимум N последних снапшотов
SNAPSHOT_MIN_INTERVAL_HOURS=24  # не создавать снапшот чаще, чем раз в N часов
SNAPSHOT_MIN_INTERVAL_MINUTES=0 # ... или дополнительно N минут
```

- **Интервал** (`SNAPSHOT_MIN_INTERVAL_HOURS` / `SNAPSHOT_MIN_INTERVAL_MINUTES`, значения суммируются): снапшот не создаётся, если последний сделан менее этого периода назад — обновляется только `latest`. `0` — создавать при каждом запуске.
- **Ретеншн по дням** (`SNAPSHOT_RETENTION_DAYS`) — удаляются снапшоты старше N дней.
- **Ретеншн по количеству** (`SNAPSHOT_RETENTION_COUNT`) — остаются всегда последние N архива, старее удаляются. `0` — не держать архивов.

Оба ограничения применяются вместе: снапшот удаляется, если он старше `SNAPSHOT_RETENTION_DAYS` **или** находится за пределами последних `SNAPSHOT_RETENTION_COUNT`. Для GitHub отдельный ZIP не создаётся — историю хранит сам Git.

## Масштабирование

```env
BACKUP_CONCURRENCY=8    # сколько статей обрабатывается параллельно
RETRY_COUNT=3           # ретраи сетевых запросов, 0 — выключить
RETRY_BACKOFF=0.5       # начальная задержка перед повтором (экспонента, сек)
```

- Статьи обрабатываются **параллельно** в пул воркеров (`BACKUP_CONCURRENCY`). Каждый воркер имеет собственную HTTP-сессию с тем же токеном — `requests.Session` не потокобезопасен, поэтому сессии изолированы.
- Сетевые запросы (включая скачивание файлов) **повторяются** на сбои соединения и 5xx — `ChunkedEncodingError`, таймауты, 429/500/502/503/504.
- Ошибка одной статьи записывается в `manifest.errors` и не останавливает остальные. При **исключениях ассетов** и `FAIL_ON_ASSET_ERROR=true` бэкап падает целиком — на большом объёме рекомендуется `FAIL_ON_ASSET_ERROR=false`, чтобы не валился весь прогон из-за одного битого файла.

## Обработка ошибок

```env
FAIL_ON_ASSET_ERROR=true
```

При `true` недоступная картинка/вложение делает весь backup неуспешным (exit code 1, `latest` не заменяется). При `false` backup завершается, ошибки записываются в `manifest.json` и лог.

Exit codes: `0` — успех, `1` — ошибка.

## Маскирование секретов

```env
REDACT=true
```

Статьи базы знаний могут содержать логины/пароли и email. При `REDACT=true` (по умолчанию) такие значения заменяются на `REDACTED` / `********` во всех выгружаемых файлах — `.md`, `.source.html`, `.metadata.json`. Это важно при публикации бэкапа в публичный git/S3. Отключить — `REDACT=false`.

## Безопасность

- Креды читаются только из environment variables, **не хранятся** в репозитории и на диске.
- Bearer-токен получается при каждом запуске и не записывается в файлы.
- Пароли и токены не выводятся в лог.
- `REDACT=true` маскирует логины/пароли/email в выгружаемом контенте.
- Бэкап содержит полное содержимое базы знаний — не публикуйте его без проверки на чувствительные данные.

## Coolify

1. Создайте Application из Git-репозитория (Dockerfile).
2. В Environment Variables укажите переменные из `.env.example`.
3. При `STORAGE_BACKEND=local` создайте persistent volume `/data/backups` и задайте `LOCAL_BACKUP_DIR=/data/backups`.
4. Создайте Scheduled Task с командой `python backup.py`.

Рекомендуемое расписание: `30 2 * * *` (раз в сутки). Расписание задаётся в Coolify, не в коде.

## Environment variables

Полный список — в [.env.example](.env.example).

Проверяются обязательные переменные в зависимости от выбранного backend:
- `local` — `MYTEAM_*`;
- `github` — + `GITHUB_TOKEN`, `GITHUB_REPOSITORY`;
- `s3` — + `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`.

## Тесты

```bash
python -m pytest tests/
```

Покрытие: безопасные имена каталогов, HTML→Markdown, локальные ссылки, пагинация, выбор backend, валидация конфигурации, маскирование секретов, ретраи/сессии, параллельная обработка статей, политика снапшотов (интервал + retention).

## Структура проекта

```text
myteam-kb-backup/
├── app/
│   ├── config.py
│   ├── logging.py
│   ├── common.py
│   ├── myteam_client.py
│   ├── redact.py
│   ├── exporter.py
│   ├── html_converter.py
│   ├── downloader.py
│   ├── manifest.py
│   ├── runner.py
│   └── storage/
│       ├── base.py
│       ├── local.py
│       ├── github.py
│       └── s3.py
├── tests/
├── backup.py
├── requirements.txt
├── Dockerfile
├── .env.example
└── LICENSE
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
