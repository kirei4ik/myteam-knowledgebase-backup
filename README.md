# myteam-kb-backup

Автономный модуль резервного копирования базы знаний сервиса «МояКоманда» через REST API.

Backup — это человекочитаемая структура каталогов, которую можно открыть обычным файловым менеджером или как Obsidian Vault:

```
knowledge-base/
└── ИТ - инструменты/
    └── Обходы блокировок/
        └── Настроить Proxy для Telegram/
            ├── Настроить Proxy для Telegram.md
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

- авторизация через `POST /api/login` (Bearer-токен получается при каждом запуске, на диск не пишется);
- полный список категорий и статей с учётом пагинации;
- HTML → Markdown (`markdownify` + `BeautifulSoup`);
- скачивание картинок/видео/вложений с заменой ссылок на локальные;
- сохранение `.source.html` и `.metadata.json`;
- `manifest.json` со счётчиками и SHA-256 файлов;
- storage backends: `local`, `github`, `s3`;
- snapshots (`latest/` + `snapshots/<timestamp>/knowledge-base.zip`);
- retention старых снапшотов;
- `--dry-run` и `--output`.

## Локальный запуск

```bash
cp .env.example .env
```

В `.env`:

```env
MYTEAM_BASE_URL=https://profitreid.ismyteam.ru
MYTEAM_EMAIL=you@company.ru
MYTEAM_PASSWORD=secret
STORAGE_BACKEND=local
LOCAL_BACKUP_DIR=./backups
```

Затем:

```bash
python backup.py
```

Результат:

```text
project/
├── backup.py
└── backups/
    └── latest/
        └── knowledge-base/
```

Вывод в консоль:

```text
[INFO] Authentication successful
[INFO] Categories loaded: 13
[INFO] Articles discovered: 22
[INFO] Processing article 1/22: ...
[INFO] Downloading image: ...
[INFO] Markdown generated
[INFO] Snapshot created
[INFO] Backup completed successfully
```

### Dry-run

```bash
python backup.py --dry-run
```

Строит полный backup в `WORK_DIR`, ничего не публикует.

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
SNAPSHOT_RETENTION_DAYS=30
```

Снапшоты старше `SNAPSHOT_RETENTION_DAYS` удаляются. Для GitHub отдельный ZIP не создаётся — историю хранит сам Git.

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

Статьи базы знаний могут содержать логины/пароли и email («Корп. почта и пароль…», «Прокси для Telegram» и т.п.). При `REDACT=true` (по умолчанию) такие значения заменяются на `REDACTED` / `********` во всех выгружаемых файлах — `.md`, `.source.html`, `.metadata.json`. Это важно при публикации бэкапа в публичный git/S3. Отключить — `REDACT=false`.

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

Пароли и токены в лог не выводятся.

## Тесты

```bash
python -m pytest tests/
```

Покрытие: безопасные имена, HTML→Markdown, локальные ссылки `<img>`, дерево категорий, пагинация, выбор backend, валидация конфигурации.

## Структура проекта

```text
myteam-kb-backup/
├── app/
│   ├── config.py
│   ├── logging.py
│   ├── common.py
│   ├── myteam_client.py
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
└── README.md
```
