import logging
import os
import re
import signal
import pathlib

from datetime import datetime
from functools import lru_cache
from hashlib import md5

from .config import Config, DbConfig
from .models import Script, ScriptState, ExecMode, ForceMode
from .psql import exec_file
from .history import (
    SQLApplyError,
    init_db,
    check_db,
    get_script_state,
    get_src_hash,
    insert_record,
    update_record,
)
from .display import CSNode, CSTree


@lru_cache(maxsize=1000)
def _natural_key(s: str) -> list[tuple[int, int | str]]:
    parts = re.split(r"(\d+)", s)
    key: list[tuple[int, int | str]] = []
    for part in parts:
        if part.isdigit():
            flag = 0 if part.startswith("0") and part != "0" else 1
            key.append((flag, int(part)))
        else:
            key.append((2, part.lower()))
    return key


def load_scripts(directory: str, pattern: str = "*.sql") -> list[Script]:
    dir_path = pathlib.Path(directory)
    scripts = []
    for f in dir_path.glob(pattern):
        if f.is_file():
            scripts.append(Script(
                name=f.name,
                content=f.read_text(encoding="utf-8"),
                path=f,
            ))
    scripts.sort(key=lambda s: _natural_key(s.name))
    return scripts


class SQLApplyTool:
    def __init__(self, config: Config):
        self.config = config
        self._stop = False
        self._setup_logging()

    def _setup_logging(self):
        logs_dir = self.config.logs_dir
        exec_logs_dir = logs_dir / "execution_logs"
        os.makedirs(logs_dir, exist_ok=True)
        os.makedirs(exec_logs_dir, exist_ok=True)

        log_file = logs_dir / f"log_{datetime.now():%Y-%m-%d}.log"

        logging.basicConfig(
            level=getattr(logging, self.config.logging_level, logging.INFO),
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8", mode="a"),
                logging.StreamHandler(),
            ],
        )

    def _log_execution(
        self,
        script_name: str,
        change_name: str,
        dbname: str,
        output: str,
    ) -> str:
        safe_name = script_name.replace("/", "_")
        filename = f"{dbname}_{change_name}_{safe_name}.log"
        path = self.config.logs_dir / "execution_logs" / filename

        entry = f"-- LOG OF {datetime.now():%Y-%m-%d %H:%M:%S}\n{output}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

        return str(path)

    def init_dbs(self, target_db: str, change_name: str | None = None):
        if target_db == "ALL":
            if not change_name:
                raise SQLApplyError(
                    "Usage: '--init --dbname <dbname>' or '<change_name> --init'"
                )
            change_path = self.config.changes_dir / change_name
            if not change_path.exists():
                raise SQLApplyError(f"Change folder not found: {change_path}")

            logging.info(f"Initializing all databases in change '{change_name}'")
            for entry in change_path.iterdir():
                if entry.is_dir():
                    db = self.config.get_db(entry.name)
                    check_db(db, check_init=False)
                    init_db(db)
        else:
            db = self.config.get_db(target_db)
            check_db(db, check_init=False)
            init_db(db)

    def show_change(self, change_name: str, pattern: str = "*.sql"):
        change_path = self.config.changes_dir / change_name
        if not change_path.exists():
            raise SQLApplyError(f"Change folder not found: {change_path}")

        root = CSNode(f"Change '{change_name}' (pattern: '{pattern}')", color="green")

        for entry in sorted(change_path.iterdir()):
            if not entry.is_dir():
                continue
            db = self.config.get_db(entry.name)
            scripts = load_scripts(str(entry), pattern)
            db_node = CSNode(f"DB '{entry.name}' ({db.host}:{db.port})", color="cyan")
            for s in scripts:
                db_node.add(CSNode(s.name))
            root.add(db_node)

        CSTree(root).display()

    @staticmethod
    def _script_hash(script: Script) -> str:
        return md5(script.content.encode("utf-8")).hexdigest()

    def _should_execute(
        self,
        script: Script,
        force_mode: ForceMode | None,
        db: DbConfig,
        change_name: str,
        dry_run: bool,
    ) -> bool:
        state = script.state

        if state == ScriptState.NEW:
            if dry_run:
                logging.info(f"'{script.name}' new execution")
            return True

        if state == ScriptState.APPLIED:
            src_hash = self._script_hash(script)
            last_hash = get_src_hash(db, change_name, script.name)
            hash_changed = last_hash and last_hash != src_hash

            if force_mode == ForceMode.ALL:
                return True

            logging.info(f"'{script.name}' already applied, skipping")

            if hash_changed:
                if force_mode == ForceMode.MD5DIFF:
                    return True
                logging.warning(
                    f"'{script.name}' MD5 changed "
                    f"(prev: {last_hash[:6]}..., curr: {src_hash[:6]}...)"
                )
            return False

        if state == ScriptState.FAILED:
            if force_mode in (ForceMode.ALL, ForceMode.ERROR):
                return True
            msg = f"'{script.name}' previously failed"
            if not dry_run:
                msg += " (use --force ALL or --force ERROR)"
            logging.error(msg)
            self._stop = True
            return False

        if state == ScriptState.IN_PROGRESS:
            log_fn = logging.warning if dry_run else logging.error
            log_fn(f"'{script.name}' has status 'in progress' in history")
            return False

        if state == ScriptState.STOPPED:
            if force_mode in (ForceMode.ALL, ForceMode.ERROR):
                return True

            src_hash = self._script_hash(script)
            last_hash = get_src_hash(db, change_name, script.name)
            if last_hash and last_hash != src_hash and force_mode == ForceMode.MD5DIFF:
                return True

            return True

        return False

    def execute_change(
        self,
        change_name: str,
        exec_mode: ExecMode = ExecMode.SINGLE_TRANSACTION,
        pattern: str = "*.sql",
        force_mode: ForceMode | None = None,
        dry_run: bool = False,
    ):
        change_path = self.config.changes_dir / change_name
        if not change_path.exists():
            raise SQLApplyError(f"Change folder not found: {change_path}")

        signal.signal(signal.SIGINT, lambda _s, _f: self._set_stop())

        db_dirs = sorted(e for e in change_path.iterdir() if e.is_dir())

        for d in db_dirs:
            check_db(self.config.get_db(d.name))

        logging.info(f"Finding files on pattern '{pattern}'...")

        for db_dir in db_dirs:
            dbname = db_dir.name
            db = self.config.get_db(dbname)
            scripts = load_scripts(str(db_dir), pattern)

            logging.info(f"Executing scripts on db '{dbname}' (Total: {len(scripts)})")
            logging.debug(
                "\n".join(f"- [{i + 1}] {s.name}" for i, s in enumerate(scripts))
            )

            for script in scripts:
                script.state = get_script_state(db, change_name, script.name)
                if script.state == ScriptState.NEW and not dry_run:
                    insert_record(db, change_name, script.name, self._script_hash(script))

            for script in scripts:
                if self._stop and not dry_run:
                    update_record(
                        db, change_name, script.name,
                        "EXECUTION_STOPPED", self._script_hash(script),
                    )
                    continue

                should = self._should_execute(script, force_mode, db, change_name, dry_run)

                if dry_run:
                    if should and script.state != ScriptState.NEW:
                        logging.info(f"'{script.name}' will be re-executed")
                    continue

                if not should:
                    continue

                result = exec_file(db=db, path=str(script.path), args=exec_mode.psql_args)

                update_record(
                    db, change_name, script.name,
                    result.status.value, self._script_hash(script),
                )

                log_path = self._log_execution(script.name, change_name, dbname, result.combined)

                if not result.ok:
                    logging.error(
                        f"Error executing '{dbname}/{script.name}'\n"
                        f"Execution log: '{log_path}'"
                    )
                    self._stop = True
                else:
                    msg = f"'{script.name}' successfully executed"
                    if force_mode:
                        msg += f" (forcing '{force_mode.value}')"
                    logging.info(msg)

            if not dry_run:
                if self._stop:
                    logging.error(f"Error executing change in db '{dbname}'")
                else:
                    logging.info(f"Executing change in db '{db.dbname}' completed")

        if not self._stop:
            logging.info("Executing change completed")

    def _set_stop(self):
        logging.info("Process interruption by user")
        self._stop = True
