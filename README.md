# PG_SQLAPPLY

A tool for managing migrations and versioning SQL scripts in PostgreSQL.

### Documentation translations
- [English](README.md)
- [Russian](README_ru.md)

## Requirements

- Python 3.10+
- PostgreSQL with `psql` installed
- Linux

## Installation

```bash
git clone https://github.com/mk-samoilov/pg_sqlapply.git
cd pg_sqlapply
```

## Configuration

Init tool for create config template:
```
python3 -m sqlapply
```

Configure `sqlapply.conf`:

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

### Connection Options

**TCP/IP with password:**
```ini
host = localhost
user = myuser
password = mypassword
```

**Unix socket (peer auth, no password):**
```ini
host = local
user = mk
password =
```

## Project Structure

```
changes/
└── <change_name>/
    └── <db_section>/
        ├── 01_schema.sql
        ├── 02_data.sql
        └── 03_indexes.sql
```

Scripts are executed in natural sort order (1, 2, 10 instead of 1, 10, 2).

## Usage

### Initialize Database

Creates `sqlapply` schema for storing execution history:

```bash
python3 -m sqlapply --init --dbname my_database

python3 -m sqlapply my_release --init
```

### View Changeset Structure

```bash
python3 -m sqlapply my_release --show
```

### Check Before Execution (dry-run)

```bash
python3 -m sqlapply my_release --check
```

### Execute Changeset

```bash
python3 -m sqlapply my_release

python3 -m sqlapply my_release --dbname my_database

python3 -m sqlapply my_release --pattern "01_*.sql"
```

### Re-execute (force)

```bash
python3 -m sqlapply my_release --force ALL

python3 -m sqlapply my_release --force ERROR

python3 -m sqlapply my_release --force MD5DIFF
```

### Execution Modes

```bash
python3 -m sqlapply my_release --mode single-transaction

python3 -m sqlapply my_release --mode on-error-stop
```

### Custom Config File

```bash
python3 -m sqlapply my_release -C /path/to/custom.conf
```

## Logs

- General logs: `logs/log_YYYY-MM-DD.log`
- Scripts executions logs: `logs/execution_logs/<db>_<change>_<script>.log`

## Work example

```bash
mkdir -p changes/release_v1/production_db

echo "CREATE TABLE users (id SERIAL PRIMARY KEY);" > changes/release_v1/production_db/01_users.sql
echo "INSERT INTO users DEFAULT VALUES;" > changes/release_v1/production_db/02_seed.sql

python3 -m sqlapply release_v1 --init

python3 -m sqlapply release_v1 --check

python3 -m sqlapply release_v1
```

