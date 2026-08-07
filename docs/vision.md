# ТЗ: модуль резервного копирования базы знаний «МояКоманда»

## 1. Цель

Разработать автономный модуль `myteam-kb-backup` для резервного копирования базы знаний сервиса «МояКоманда» через REST API.

Результат резервного копирования должен быть человекочитаемым и не зависеть от работоспособности исходной системы.

После выгрузки базу знаний должно быть возможно открыть обычным файловым менеджером или как Obsidian Vault.

Основная логическая модель:

* категория базы знаний → папка;
* подкатегория → вложенная папка;
* статья → отдельная папка;
* текст статьи → Markdown-файл;
* картинки внутри статьи → локальные файлы рядом со статьёй;
* прикреплённые файлы → локальные файлы рядом со статьёй;
* ссылки на изображения и файлы в Markdown должны быть относительными.

---

# 2. Технология

Предпочтительно:

* Python 3.12+;
* Docker;
* конфигурация через environment variables;
* минимальное количество внешних зависимостей;
* структурированное логирование в stdout/stderr.

Модуль должен одинаково запускаться:

```bash
python backup.py
```

локально, внутри Docker и как Scheduled Task в Coolify.

---

# 3. Источник данных

API:

```text
https://profitreid.ismyteam.ru
```

URL должен быть вынесен в настройку:

```env
MYTEAM_BASE_URL=https://profitreid.ismyteam.ru
```

## 3.1. Авторизация

Использовать:

```http
POST /api/login-mobile
```

Учётные данные:

```env
MYTEAM_EMAIL=
MYTEAM_PASSWORD=
```

Модуль при каждом запуске должен самостоятельно получать Bearer Token.

Токен не хранить постоянно на диске.

Пароли, токены, S3 credentials и GitHub credentials запрещено записывать в лог.

---

# 4. Получение структуры базы знаний

Использовать API базы знаний.

Из API уже подтверждено получение:

* дерева категорий;
* списка статей;
* `id` статьи;
* категории статьи;
* даты создания;
* даты изменения;
* автора;
* содержимого статьи в HTML;
* прикреплённых файлов;
* других метаданных.

Не предполагать, что список статей помещается на одну страницу.

API использует пагинацию, поэтому необходимо получить **все страницы** до `totalPages`.

---

# 5. Формирование структуры каталогов

Например исходная структура:

```text
ИТ - инструменты
└── Обходы блокировок
    └── Настроить Proxy для Telegram
```

должна превратиться в:

```text
knowledge-base/
└── ИТ - инструменты/
    └── Обходы блокировок/
        └── Настроить Proxy для Telegram/
            ├── Настроить Proxy для Telegram.md
            ├── image-1.png
            ├── image-2.png
            ├── .source.html
            └── .metadata.json
```

Если у статьи есть вложения:

```text
knowledge-base/
└── Категория/
    └── Название статьи/
        ├── Название статьи.md
        ├── instruction.pdf
        ├── template.xlsx
        ├── image-1.png
        ├── .source.html
        └── .metadata.json
```

---

# 6. Безопасные имена файлов

Названия категорий и статей используются как имена каталогов.

Необходимо очищать символы, несовместимые с файловыми системами:

```text
/ \ : * ? " < > |
```

Не допускать:

* выхода за пределы backup-каталога через `../`;
* абсолютных путей;
* конфликтов одинаковых имён.

При конфликте имён использовать ID объекта.

Например:

```text
Название статьи [id-123]/
```

ID статьи должен всегда сохраняться в metadata независимо от имени каталога.

---

# 7. HTML → Markdown

Поле `content` API содержит HTML.

Не сохранять HTML как основной пользовательский формат.

Необходимо преобразовать:

```text
HTML → Markdown
```

Сохранять по возможности:

* заголовки;
* абзацы;
* жирный текст;
* курсив;
* ссылки;
* маркированные списки;
* нумерованные списки;
* таблицы;
* blockquote;
* `<br>`;
* horizontal rule;
* изображения.

Предпочтительно использовать готовую библиотеку, например `markdownify`, с дополнительной обработкой HTML через BeautifulSoup при необходимости.

---

# 8. Markdown статьи

Начало файла должно содержать YAML front matter.

Пример:

```markdown
---
myteam_id: 8
title: "Настроить Proxy для Telegram"
category_id: 7
category: "Обходы блокировок"
author: "Имя автора"
created: "2026-05-04 13:19"
updated: "2026-07-20 11:59"
---

# Настроить Proxy для Telegram

Текст статьи...
```

Если доступны теги, добавить:

```yaml
tags:
  - tag1
  - tag2
```

---

# 9. Картинки внутри статьи

Картинки могут находиться непосредственно внутри HTML:

```html
<img src="/storage/public/modules/knowledge-base/post-content/xxx.png">
```

При обработке статьи необходимо:

1. найти все `<img>`;
2. получить `src`;
3. сформировать абсолютный URL относительно `MYTEAM_BASE_URL`, если URL относительный;
4. скачать изображение;
5. сохранить его в каталог статьи;
6. заменить ссылку в Markdown на относительную.

Было:

```html
<img src="/storage/.../abc.png">
```

Должно стать:

```markdown
![](abc.png)
```

Таким образом Markdown не должен зависеть от сайта «МояКоманда».

Не использовать внешние URL сервиса там, где файл можно сохранить локально.

---

# 10. Другие встроенные ресурсы

При парсинге HTML проверить также:

```html
<a href="">
<video src="">
<source src="">
```

Если URL указывает на внутреннее файловое хранилище «МояКоманда», такой ресурс также желательно скачать и заменить ссылку на локальную.

Не скачивать произвольные внешние сайты.

---

# 11. Прикреплённые файлы

Поле:

```json
"files"
```

может содержать прикреплённые к статье файлы.

Использовать соответствующий API «Операции с файлами / downloadFile».

Каждый файл необходимо:

1. скачать;
2. сохранить в каталог соответствующей статьи;
3. сохранить оригинальное имя, если это безопасно;
4. добавить ссылку на файл в Markdown.

В конце Markdown добавить:

```markdown
## Вложения

- [Инструкция.pdf](Инструкция.pdf)
- [Шаблон.xlsx](Шаблон.xlsx)
```

Если вложений нет, раздел не создавать.

---

# 12. Сохранение исходных данных

Markdown является основным пользовательским форматом, но преобразование HTML → Markdown потенциально может быть неполным.

Поэтому рядом со статьёй обязательно сохранять:

```text
.source.html
.metadata.json
```

`.source.html` содержит оригинальное значение `content` без преобразований.

`.metadata.json` содержит максимально полный оригинальный JSON статьи, полученный от API.

Это позволит в будущем восстановить информацию, которая могла потеряться при преобразовании в Markdown.

---

# 13. Режимы хранения

Способ хранения задаётся через:

```env
STORAGE_BACKEND=local
```

Допустимые значения:

```text
local
github
s3
```

Логика формирования базы знаний должна быть полностью независима от конкретного storage backend.

Предусмотреть интерфейс/абстракцию:

```python
StorageBackend
```

примерно с методом:

```python
store(backup_path, metadata)
```

Реализовать три backend.

---

# 14. Local backend

```env
STORAGE_BACKEND=local
LOCAL_BACKUP_DIR=./backups
```

Для локальной разработки по умолчанию:

```text
./backups
```

Например:

```text
project/
├── backup.py
└── backups/
    └── latest/
        └── knowledge-base/
```

Для Docker рекомендуется:

```env
LOCAL_BACKUP_DIR=/data/backups
```

В Docker `/data/backups` должен быть persistent volume.

Например:

```text
Host / Coolify persistent storage
          ↕
/data/backups
```

**Не рассчитывать на файловую систему самого контейнера**, поскольку после пересоздания контейнера она может быть потеряна.

Приложение не должно само определять, работает оно в Docker или нет.

Оно просто использует:

```env
LOCAL_BACKUP_DIR
```

---

# 15. GitHub backend

```env
STORAGE_BACKEND=github

GITHUB_TOKEN=
GITHUB_REPOSITORY=organization/repository
GITHUB_BRANCH=main
GITHUB_BACKUP_PATH=knowledge-base
```

Опционально:

```env
GITHUB_COMMIT_AUTHOR_NAME=MyTeam Backup
GITHUB_COMMIT_AUTHOR_EMAIL=
```

Логика:

1. сформировать backup во временной локальной директории;
2. получить актуальное состояние целевого Git-репозитория;
3. заменить содержимое каталога `GITHUB_BACKUP_PATH`;
4. выполнить commit;
5. выполнить push.

Commit message:

```text
MyTeam KB backup: 2026-08-07 02:30
```

Если содержимое не изменилось, новый commit не создавать.

GitHub backend должен давать историю изменений базы знаний через Git.

Пример:

```text
repository/
└── knowledge-base/
    ├── ИТ - инструменты/
    └── Общая информация компании/
```

### Ограничение GitHub

GitHub следует считать дополнительным способом хранения, особенно удобным для:

* Markdown;
* истории изменения статей;
* небольших картинок;
* небольших документов.

Он не должен предполагаться оптимальным хранилищем для большого количества крупных бинарных файлов.

Архитектура должна позволять в любой момент переключиться:

```env
STORAGE_BACKEND=s3
```

без изменения логики выгрузки базы знаний.

---

# 16. S3 backend

Настройки:

```env
STORAGE_BACKEND=s3

S3_ENDPOINT_URL=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_BUCKET=
S3_REGION=
S3_PREFIX=myteam-kb
```

Поддержать S3-compatible storage, а не только AWS.

SSL:

```env
S3_VERIFY_SSL=true
```

Результат должен загружаться в S3.

---

# 17. Формат версий backup

Добавить настройку:

```env
BACKUP_MODE=snapshot
```

Для первой версии достаточно режима `snapshot`.

Формировать:

```text
latest/
snapshots/
```

Пример:

```text
myteam-kb/
├── latest/
│   └── knowledge-base/
│       └── ...
│
└── snapshots/
    └── 2026-08-07T023000/
        └── knowledge-base.zip
```

`latest` содержит текущее состояние в распакованном виде, если backend это поддерживает.

`snapshots` содержит архив предыдущего состояния.

Для GitHub отдельный ZIP snapshot необязателен, поскольку историю предоставляет сам Git.

Для `local` и `s3` snapshot создавать.

---

# 18. Настройки snapshot

Вынести в env:

```env
CREATE_SNAPSHOT=true
SNAPSHOT_FORMAT=zip
```

Опционально:

```env
SNAPSHOT_RETENTION_DAYS=30
```

Если retention реализуется в первой версии:

* удалять snapshots старше указанного количества дней;
* `latest` никогда не удалять.

Если retention усложняет первую реализацию, выделить его отдельным модулем и оставить TODO.

---

# 19. Временные файлы

Добавить:

```env
WORK_DIR=/tmp/myteam-kb-backup
```

На каждом запуске:

1. создать чистую временную рабочую директорию;
2. сформировать там полный backup;
3. проверить результат;
4. только после успешного завершения передавать данные storage backend;
5. после завершения удалить временную директорию.

Нельзя сначала удалять предыдущий успешный backup, а потом начинать формировать новый.

---

# 20. Целостность

Backup считается успешным только если:

* успешно получены все страницы списка статей;
* каждая статья успешно загружена;
* все доступные встроенные картинки скачаны;
* все доступные прикреплённые файлы скачаны;
* сформирован Markdown каждой статьи;
* результат передан storage backend.

Создать:

```text
manifest.json
```

Пример:

```json
{
  "created_at": "2026-08-07T02:30:00+03:00",
  "source": "https://profitreid.ismyteam.ru",
  "categories": 13,
  "articles": 22,
  "images": 35,
  "attachments": 8,
  "errors": []
}
```

Также желательно сохранять SHA-256 файлов.

---

# 21. Обработка ошибок

По умолчанию backup должен быть атомарным с точки зрения публикации.

Если одна статья или обязательный файл не выгрузились:

* вывести понятную ошибку;
* вернуть ненулевой exit code;
* **не заменять `latest` предыдущего успешного backup**.

Добавить:

```env
FAIL_ON_ASSET_ERROR=true
```

При:

```env
FAIL_ON_ASSET_ERROR=true
```

недоступная картинка или вложение делает весь backup неуспешным.

При:

```env
FAIL_ON_ASSET_ERROR=false
```

backup завершается, но ошибка обязательно записывается в `manifest.json` и лог.

---

# 22. Логирование

Пример:

```text
[INFO] Authentication successful
[INFO] Categories loaded: 13
[INFO] Articles discovered: 22
[INFO] Processing article 1/22: ...
[INFO] Downloaded image: ...
[INFO] Downloaded attachment: ...
[INFO] Markdown generated
[INFO] Snapshot created
[INFO] Uploading to s3
[INFO] Backup completed successfully
```

При ошибке:

```text
[ERROR] Article 15 attachment download failed: ...
```

В логах не выводить:

* пароль;
* Bearer Token;
* GitHub Token;
* S3 Secret Key.

---

# 23. Exit codes

Минимум:

```text
0 = backup выполнен успешно
1 = backup завершился ошибкой
```

Это необходимо для Coolify Scheduled Tasks.

---

# 24. Ручной запуск

Основная команда:

```bash
python backup.py
```

Опционально добавить:

```bash
python backup.py --dry-run
```

`--dry-run`:

* получает данные из API;
* строит backup в `WORK_DIR`;
* не отправляет результат в GitHub/S3;
* выводит статистику.

Также полезно:

```bash
python backup.py --output ./test-backup
```

для локальной разработки.

CLI-параметры могут переопределять соответствующие env-настройки.

---

# 25. Docker

Создать `Dockerfile`.

Контейнер должен запускать:

```bash
python backup.py
```

Не помещать cron внутрь контейнера.

Планировщиком занимается Coolify.

Пример Docker volume:

```text
/data/backups
```

Если используется:

```env
STORAGE_BACKEND=local
LOCAL_BACKUP_DIR=/data/backups
```

в Coolify обязательно подключается persistent storage.

---

# 26. Запуск по расписанию

На production запуск осуществляется через Coolify Scheduled Task.

Команда:

```bash
python backup.py
```

Расписание задаётся в самом Coolify, а не внутри приложения.

Рекомендуемое начальное расписание:

```cron
30 2 * * *
```

один раз в сутки.

Расписание **не должно быть захардкожено в код**.

---

# 27. Environment variables

Подготовить `.env.example`.

Пример:

```env
# MyTeam
MYTEAM_BASE_URL=https://profitreid.ismyteam.ru
MYTEAM_EMAIL=
MYTEAM_PASSWORD=

# Storage
STORAGE_BACKEND=local

# Local
LOCAL_BACKUP_DIR=./backups

# Work
WORK_DIR=/tmp/myteam-kb-backup

# Backup
CREATE_SNAPSHOT=true
SNAPSHOT_FORMAT=zip
SNAPSHOT_RETENTION_DAYS=30
FAIL_ON_ASSET_ERROR=true

# GitHub
GITHUB_TOKEN=
GITHUB_REPOSITORY=
GITHUB_BRANCH=main
GITHUB_BACKUP_PATH=knowledge-base
GITHUB_COMMIT_AUTHOR_NAME=MyTeam Backup
GITHUB_COMMIT_AUTHOR_EMAIL=

# S3
S3_ENDPOINT_URL=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_BUCKET=
S3_REGION=
S3_PREFIX=myteam-kb
S3_VERIFY_SSL=true
```

Проверять обязательные переменные в зависимости от выбранного backend.

Например при:

```env
STORAGE_BACKEND=local
```

не требовать S3 и GitHub credentials.

При:

```env
STORAGE_BACKEND=github
```

обязательно проверить:

```text
GITHUB_TOKEN
GITHUB_REPOSITORY
```

---

# 28. Архитектура проекта

Не писать всё в одном `backup.py`.

Пример структуры:

```text
myteam-kb-backup/
├── app/
│   ├── config.py
│   ├── myteam_client.py
│   ├── exporter.py
│   ├── html_converter.py
│   ├── downloader.py
│   ├── manifest.py
│   │
│   └── storage/
│       ├── base.py
│       ├── local.py
│       ├── github.py
│       └── s3.py
│
├── tests/
├── backup.py
├── requirements.txt
├── Dockerfile
├── .env.example
├── .gitignore
└── README.md
```

Разделение ответственности:

```text
myteam_client
    ↓
Получение данных API

exporter
    ↓
Построение структуры базы знаний

html_converter
    ↓
HTML → Markdown

downloader
    ↓
Картинки и вложения

storage
    ↓
local / github / s3
```

---

# 29. Тестируемость

Добавить unit tests минимум для:

* safe filename;
* HTML → Markdown;
* преобразования `<img>` в локальную ссылку;
* построения дерева категорий;
* пагинации;
* выбора storage backend;
* проверки конфигурации.

API-вызовы должны быть отделены от бизнес-логики, чтобы их можно было mock'ать.

---

# 30. README

README должен содержать:

## Локальный запуск

```bash
cp .env.example .env
```

```env
STORAGE_BACKEND=local
LOCAL_BACKUP_DIR=./backups
```

затем:

```bash
python backup.py
```

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

## GitHub

Пример необходимых переменных.

## S3

Пример необходимых переменных.

## Coolify

Описать:

1. создание приложения;
2. подключение Git-репозитория;
3. Environment Variables;
4. при local backend создание persistent volume `/data/backups`;
5. создание Scheduled Task:

```bash
python backup.py
```

---

# 31. Что не делать

Необходимо явно избежать следующих решений:

* не хранить credentials в исходном коде;
* не хранить постоянный Bearer Token;
* не использовать ID перебором `1..N` вместо списка статей API;
* не рассчитывать, что API отдаёт только одну страницу;
* не оставлять картинки Markdown связанными с `profitreid.ismyteam.ru`;
* не считать `files` единственным источником медиа;
* не хранить backup только внутри ephemeral filesystem Docker-контейнера;
* не заменять успешный `latest` незавершённым backup;
* не превращать HTML в plain text с потерей структуры;
* не завязывать exporter на конкретный storage backend.

---

# 32. Критерии готовности первой версии

MVP считается готовым, если:

1. Приложение успешно авторизуется в «МояКоманда».
2. Получает полный список категорий.
3. Получает полный список статей с учётом пагинации.
4. Загружает каждую статью.
5. Создаёт дерево директорий категорий.
6. Для каждой статьи создаёт отдельную папку.
7. Преобразует HTML статьи в Markdown.
8. Скачивает изображения из HTML.
9. Заменяет ссылки на изображения относительными.
10. Скачивает обычные вложения.
11. Сохраняет `.source.html`.
12. Сохраняет `.metadata.json`.
13. Создаёт `manifest.json`.
14. Работает с `STORAGE_BACKEND=local`.
15. Работает с `STORAGE_BACKEND=github`.
16. Работает с `STORAGE_BACKEND=s3`.
17. Собирается в Docker.
18. Возвращает правильный exit code.
19. Может запускаться вручную одной командой.
20. Может запускаться через Coolify Scheduled Task той же командой.

---

# 33. Приоритет реализации

Реализовывать последовательно:

### Этап 1

API + local backend:

```text
MyTeam
→ выгрузка
→ Markdown
→ картинки
→ файлы
→ локальная папка
```

### Этап 2

GitHub backend:

```text
готовая локальная структура
→ Git commit
→ Git push
```

### Этап 3

S3 backend:

```text
готовая локальная структура
→ latest
→ ZIP snapshot
→ S3
```

### Этап 4

Улучшения:

* retention;
* SHA-256;
* оптимизация скачивания неизменённых файлов;
* дополнительные проверки целостности;
* уведомления.

Главный архитектурный принцип:

> Сначала сформировать полностью автономную файловую копию базы знаний в рабочем каталоге. Только после этого выбранный `StorageBackend` решает, куда эту копию сохранить.
