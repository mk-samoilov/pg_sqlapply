# PG_SQLAPPLY

Инструмент для управления миграциями и версионирования SQL-скриптов в PostgreSQL.

### Переводы документации:
- [Английский](README.md)
- [Русский](README_ru.md)

## Требования

- Python 3.10+
- PostgreSQL с установленным `psql`
- Linux

## Установка

```bash
git clone https://github.com/mk-samoilov/pg_sqlapply.git
cd pg_sqlapply
```

## Конфигурация

Инициализация для создания шаблона конфига:
```
python3 -m sqlapply
```

Настройте `sqlapply.conf`:

```ini
[DEFAULT]
logging_level = INFO

[my_database]
host = localhost
port = 5432
user = myuser
password = mypassword
dbname = mydb
```

### Варианты подключения

**TCP/IP с паролем:**
```ini
host = localhost
user = myuser
password = mypassword
```

**Unix-сокет (peer-аутентификация, без пароля):**
```ini
host = local
user = mk
password =
```

## Структура проекта

```
changes/
└── <имя_ченжсета>/
    └── <секция_бд>/
        ├── 01_schema.sql
        ├── 02_data.sql
        └── 03_indexes.sql
```

Скрипты выполняются в порядке естественной сортировки (1, 2, 10 вместо 1, 10, 2).

## Использование

### Инициализация базы данных

Создаёт схему `sqlapply` для хранения истории выполнения:

```bash
python3 -m sqlapply --init --dbname my_database

python3 -m sqlapply my_release --init
```

### Просмотр структуры ченжсета

```bash
python3 -m sqlapply my_release --show
```

### Проверка перед выполнением (dry-run)

```bash
python3 -m sqlapply my_release --check
```

### Выполнение ченжсета

```bash
python3 -m sqlapply my_release

python3 -m sqlapply my_release --dbname my_database

python3 -m sqlapply my_release --pattern "01_*.sql"
```

### Повторное выполнение (force)

```bash
python3 -m sqlapply my_release --force ALL

python3 -m sqlapply my_release --force ERROR

python3 -m sqlapply my_release --force MD5DIFF
```

### Режимы выполнения

```bash
python3 -m sqlapply my_release --mode single-transaction

python3 -m sqlapply my_release --mode on-error-stop
```

### Свой конфиг-файл

```bash
python3 -m sqlapply my_release -C /path/to/custom.conf
```

## Логи

- Общие логи: `logs/log_YYYY-MM-DD.log`
- Логи выполнения скриптов: `logs/execution_logs/<db>_<change>_<script>.log` + в скрипте разделение по запускам

## Пример работы

```bash
mkdir -p changes/release_v1/production_db

echo "CREATE TABLE users (id SERIAL PRIMARY KEY);" > changes/release_v1/production_db/01_users.sql
echo "INSERT INTO users DEFAULT VALUES;" > changes/release_v1/production_db/02_seed.sql

python3 -m sqlapply release_v1 --init

python3 -m sqlapply release_v1 --check

python3 -m sqlapply release_v1
```
