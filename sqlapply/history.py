import logging
from pathlib import Path

from .config import DbConfig
from .models import ScriptState, ExecMode
from .psql import exec_sql, exec_file


SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"

_SQL_CACHE: dict[str, str] = {}


def _sql(name: str) -> str:
    if name not in _SQL_CACHE:
        _SQL_CACHE[name] = (SCRIPTS_DIR / name).read_text(encoding="utf-8")
    return _SQL_CACHE[name]


def _fmt(template: str, **kwargs: str) -> str:
    result = template
    for key, value in kwargs.items():
        result = result.replace(f"%{key}", value)
    return " ".join(result.split()).strip()


class SQLApplyError(Exception):
    pass


class ConnectionError_(SQLApplyError):
    pass


class NotInitializedError(SQLApplyError):
    pass


def init_db(db: DbConfig) -> None:
    src = str(SCRIPTS_DIR / "init_sqlapply_schema.sql")
    result = exec_file(db=db, path=src, args=ExecMode.SINGLE_TRANSACTION.psql_args)

    already_exists_notices = [
        "Schema sqlapply already exists.",
        "Sequence sqlapply.sqlapply_history_seq already exists.",
        "Table sqlapply.sqlapply_history already exists.",
    ]

    if result.combined:
        if all(notice in result.stderr for notice in already_exists_notices):
            logging.info(f"Database '{db.dbname}' already initialized")
            return
        for line in result.stderr.splitlines():
            if not line:
                continue
            if "NOTICE:" in line:
                logging.info(line)
            elif line not in already_exists_notices:
                logging.error(line)

    if result.ok:
        logging.info(f"Database '{db.dbname}' initialized successfully")


def check_db(db: DbConfig, check_init: bool = True) -> None:
    sql = _fmt(_sql("get_sqla_history.sql"))
    result = exec_sql(db=db, sql=sql, args=ExecMode.SINGLE_TRANSACTION.psql_args)

    connect_errors = [
        "psql: error: connection to server at",
        "psql: error: connection to server on socket",
        "FATAL:  Peer authentication failed",
        "FATAL:  password authentication failed",
        "FATAL:  role",
        "FATAL:  database",
    ]

    if not result.ok:
        if any(err in result.combined for err in connect_errors):
            raise ConnectionError_(f"Connection error: {db.dbname} ({db.host}:{db.port})")
        if not check_init:
            return
        if "does not exist" in result.combined:
            raise NotInitializedError(
                f"Database '{db.dbname}' not initialized (use '--init --dbname {db.dbname}')"
            )


def get_script_state(db: DbConfig, change_name: str, script_file: str) -> ScriptState:
    sql = _fmt(
        _sql("get_status_sqla_rec.sql"),
        change_name=change_name,
        script_file=script_file,
    )
    result = exec_sql(db=db, sql=sql, args="-t -A")

    if not result.ok or not result.stdout.strip():
        return ScriptState.NEW

    return ScriptState.from_db_status(result.stdout.strip())


def get_src_hash(db: DbConfig, change_name: str, script_name: str) -> str | None:
    sql = _fmt(
        _sql("get_src_hash.sql"),
        chg_name=change_name,
        script_name=script_name,
    )
    result = exec_sql(db=db, sql=sql, args="-t -A")

    if not result.ok:
        logging.error(f"Failed to get hash for {script_name} in {change_name}: {result.stderr}")
        return None
    if not result.stdout.strip():
        return None
    return result.stdout.strip()


def insert_record(db: DbConfig, change_name: str, script_file: str, checksum: str) -> None:
    sql = _fmt(
        _sql("insert_sqla_rec.sql"),
        change_name=change_name,
        script_file=script_file,
        status="IN_PROGRESS",
        src_checksum=checksum,
    )
    result = exec_sql(db=db, sql=sql, args=ExecMode.SINGLE_TRANSACTION.psql_args)

    if not result.ok:
        raise NotInitializedError(
            f"Database '{db.dbname}' not initialized (use '--init --dbname {db.dbname}')"
        )


def update_record(
    db: DbConfig,
    change_name: str,
    script_file: str,
    status: str,
    checksum: str,
) -> None:
    sql = _fmt(
        _sql("update_sqla_rec.sql"),
        change_name=change_name,
        script_file=script_file,
        new_status=status,
        new_hash=checksum,
    )
    result = exec_sql(db=db, sql=sql, args=ExecMode.SINGLE_TRANSACTION.psql_args)

    if not result.ok:
        raise SQLApplyError(f"Failed to update history record:\n{result.combined}")
