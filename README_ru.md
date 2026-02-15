# PG_SQLAPPLY

Инструмент для управления миграциями и версионирования SQL-скриптов в PostgreSQL.

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
python3 -m sql_apply
```

Настройте `sql_apply.conf`:

```ini
[DEFAULT]
logging_level = INFO

[my_database]
host = localhost          # или "local" для Unix-сокета
port = 5432
user = myuser
password = mypassword     # можно оставить пустым для peer-аутентификации
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
user = mk                 # должен совпадать с системным пользователем
password =
```

## Структура проекта

```
changes/
└── <имя_ченжсета>/          # Имя ченжсета (релиза)
    └── <секция_бд>/         # Имя секции из конфига
        ├── 01_schema.sql
        ├── 02_data.sql
        └── 03_indexes.sql
```

Скрипты выполняются в порядке естественной сортировки (1, 2, 10 вместо 1, 10, 2).

## Использование

### Инициализация базы данных

Создаёт схему `sqlapply` для хранения истории выполнения:

```bash
# Инициализация конкретной базы данных
python3 -m sql_apply --init --dbname my_database

# Или инициализация всех баз из ченжсета
python3 -m sql_apply my_release --init
```

### Просмотр структуры ченжсета

```bash
python3 -m sql_apply my_release --show
```

### Проверка перед выполнением (dry-run)

```bash
python3 -m sql_apply my_release --check
```

### Выполнение ченжсета

```bash
# Выполнить все скрипты
python3 -m sql_apply my_release

# Только для конкретной базы данных
python3 -m sql_apply my_release --dbname my_database

# С фильтром по шаблону
python3 -m sql_apply my_release --pattern "01_*.sql"
```

### Повторное выполнение (force)

```bash
# Перевыполнить все скрипты
python3 -m sql_apply my_release --force ALL

# Перевыполнить только упавшие скрипты
python3 -m sql_apply my_release --force ERROR

# Перевыполнить изменённые скрипты (по MD5)
python3 -m sql_apply my_release --force MD5DIFF
```

### Режимы выполнения

```bash
# Одна транзакция, откат при ошибке (по умолчанию)
python3 -m sql_apply my_release --mode single-transaction

# Остановка при ошибке, без отката
python3 -m sql_apply my_release --mode on-error-stop
```

### Свой конфиг-файл

```bash
python3 -m sql_apply my_release -C /path/to/custom.conf
```

## Логи

- Общие логи: `logs/log_YYYY-MM-DD.log`
- Логи выполнения скриптов: `logs/execution_logs/<db>_<change>_<script>.log`

## Пример работы

```bash
# 1. Создать структуру
mkdir -p changes/release_v1/production_db

# 2. Добавить скрипты
echo "CREATE TABLE users (id SERIAL PRIMARY KEY);" > changes/release_v1/production_db/01_users.sql
echo "INSERT INTO users DEFAULT VALUES;" > changes/release_v1/production_db/02_seed.sql

# 3. Настроить (добавить секцию [production_db] в конфиг)

# 4. Инициализировать базу данных
python3 -m sql_apply release_v1 --init

# 5. Проверить
python3 -m sql_apply release_v1 --check

# 6. Выполнить
python3 -m sql_apply release_v1
```
