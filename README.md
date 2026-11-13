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
    │   ├── report.md
    │   ├── manifest.json
    │   └── knowledge-base/
    └── snapshots/
        └── <timestamp>/
            └── knowledge-base.zip
```

`latest/` — актуальный бэкап. `report.md` — человекочитаемый отчёт о прогоне (статус, время, счётчики, список ошибок); он же и `manifest.json` вкладываются в снапшот-архив.

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
  myteam-kb-backup python backup.py
```

Контейнер по умолчанию «спит» (`sleep infinity`); бэкап запускается явным вызовом `python backup.py` (аргументы переопределяют CMD).

В `docker-compose`/Coolify persistent volume `/data/backups` требуется только при `STORAGE_BACKEND=local`; для S3 и GitHub не нужен.

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

S3 — объектное хранилище. Сервис выгружает в него актуальную копию (`latest/`) и архивы предыдущих копий (`snapshots/`). Подойдут AWS S3 и совместимые сервисы, например MinIO или S3-хранилище другого провайдера.

### Пример заполнения переменных

```env
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=https://s3.example-provider.ru
S3_ACCESS_KEY_ID=EXAMPLEACCESSKEY
S3_SECRET_ACCESS_KEY=replace-with-your-secret-key
S3_BUCKET=myteam-knowledgebase-backup
S3_REGION=ru-1
S3_PREFIX=myteam-kb
S3_VERIFY_SSL=true
```

**Это пример, а не готовые реквизиты:** `s3.example-provider.ru`, `ru-1` и ключи здесь вымышленные. Реальные значения возьмите в панели своего S3-провайдера.

| Переменная | Что указывать |
| --- | --- |
| `STORAGE_BACKEND` | `s3` для выгрузки в объектное хранилище; также поддерживаются `local` и `github` |
| `S3_ENDPOINT_URL` | **Адрес S3 API**, например `https://s3.example-provider.ru`. Найдите поле «Endpoint», «S3 API URL» или «Адрес подключения» в панели провайдера. Укажите `https://`, при необходимости порт (`https://host:9000`), **без имени бакета, пути к папке и ссылки на веб-консоль**. Для обычного AWS S3 можно оставить пустым: boto3 выберет стандартный endpoint |
| `S3_ACCESS_KEY_ID` | Access Key ID от S3-провайдера: идентификатор ключа доступа, **не** логин от панели |
| `S3_SECRET_ACCESS_KEY` | Secret Access Key, выдаваемый вместе с Access Key ID. Не публикуйте в Git и логах |
| `S3_BUCKET` | **Точное имя уже созданного бакета**, например `myteam-knowledgebase-backup`. Здесь не нужен URL или путь |
| `S3_REGION` | Регион из настроек провайдера, например условный `ru-1`. Для AWS укажите действительный регион бакета (например `eu-central-1`); у некоторых совместимых провайдеров регион можно не указывать |
| `S3_PREFIX` | Папка *внутри* бакета. По умолчанию `myteam-kb`; если хотите писать прямо в корень бакета, явно установите `S3_PREFIX=` |
| `S3_VERIFY_SSL` | `true` (по умолчанию): проверять TLS-сертификат. `false` снижает безопасность, для обычного подключения не используйте |

**Как найти endpoint:** откройте настройки бакета или раздел S3 API/подключения у провайдера. Нужен серверный адрес для S3-клиентов, а не URL браузера с файловым менеджером. Если провайдер показывает отдельные URL для API, публичной раздачи и панели управления, выбирайте **API endpoint**.

### Куда будут складываться файлы

**По умолчанию**, если `S3_PREFIX` не задан, используется `myteam-kb`. Это сохраняет прежнее поведение:

```text
myteam-knowledgebase-backup/       # S3_BUCKET
└── myteam-kb/                     # S3_PREFIX (по умолчанию)
    ├── latest/
    │   ├── knowledge-base/
    │   ├── manifest.json
    │   └── report.md
    └── snapshots/
        └── <timestamp>/
            └── knowledge-base.zip
```

Если бакет создан специально под этот бэкап, дополнительная папка не обязательна. Явно задайте **пустое значение**, не `/` и не имя бакета:

```env
S3_BUCKET=myteam-knowledgebase-backup
S3_PREFIX=
```

Тогда файлы будут лежать в корне бакета:

```text
myteam-knowledgebase-backup/
├── latest/
│   ├── knowledge-base/
│   ├── manifest.json
│   └── report.md
└── snapshots/
    └── <timestamp>/
        └── knowledge-base.zip
```

**Важно:** отсутствие переменной `S3_PREFIX` и явно заданное `S3_PREFIX=` — разные случаи. При отсутствии применяется значение по умолчанию `myteam-kb`; при пустом значении дополнительный уровень не создаётся. В Coolify создайте переменную `S3_PREFIX` с пустым значением, а не удаляйте её.

Бакет необходимо создать заранее; учётные данные должны иметь права на запись, чтение списка объектов и удаление старых снапшотов в указанном пути. Перед использованием retention проверьте, что бакет или префикс не используется для чужих файлов с совпадающими путями `snapshots/`.

### Другие поддерживаемые способы хранения

S3 не обязателен. `STORAGE_BACKEND=local` сохраняет резервную копию на диск (для Docker/Coolify нужен persistent volume), а `STORAGE_BACKEND=github` публикует Markdown и вложения в Git-репозиторий. Примеры находятся в разделах «Quick Start» и «GitHub backend» выше.

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

1. Создайте Application из Git-репозитория (Dockerfile). Контейнер по умолчанию «спит» (`sleep infinity`) — всю работу выполняет Scheduled Task.
2. В Environment Variables укажите переменные из `.env.example`.

   ### Volume — когда нужен

   Volume `/data/backups` нужен **только** для `STORAGE_BACKEND=local` и для `s3`/`github` **не требуется**: сборка backup идёт во временный `WORK_DIR` (по умолчанию `/tmp`), а в S3/GitHub публикуется в том же прогоне — постоянное хранилище в контейнере не участвует.

3. При `STORAGE_BACKEND=local` **обязательно** создайте persistent volume и смонтируйте его в `/data/backups`, а в env задайте `LOCAL_BACKUP_DIR=/data/backups`.

   Без volume бэкапы писались бы в `./backups` относительно `WORKDIR /app` — то есть в локальный бэкап в эфемерной файловой системе контейнера `/app/backups`, которая исчезает при редеплое/рестарте. Volume в Coolify: Application → Storage → Add Volume, mount path `/data/backups`. Заодно это место будет доступно через S3/SFTP, если нужно выгрузить копию вручную.
4. Создайте Scheduled Task с командой `python backup.py`. Логи прогона смотрите в Logs задачи (весь INFO/ERROR вывод).

   Поле контейнера/службы Coolify заполняет автоматически (имя вида `{project}-{environment}-{app}`) — вводить вручную не нужно, задача выполняется в том же контейнере приложения.

Рекомендуемое расписание: `30 2 * * *` (раз в сутки). Расписание задаётся в Coolify, не в коде.

Образ универсален: для одноразового прогона локально выполните `docker run --rm <image> python backup.py` (аргументы переопределяют CMD).

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
│   ├── report.py
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
