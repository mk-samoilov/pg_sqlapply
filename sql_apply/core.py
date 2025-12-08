import logging
import os
import pathlib
import importlib
import re
import sys
import signal

from configparser import SectionProxy
from functools import lru_cache
from hashlib import md5
from datetime import datetime
from argparse import Namespace
from threading import Lock
from typing import List, Tuple, Union, Any

from .conf_api import load_config
from .psql_api import execute_sql_file, execute_sql_string
from .console_schemes_lib import CSNode, CSTree


@lru_cache(maxsize=1000)
def natural_key(s: str) -> List[Tuple[int, Union[int, str]]]:
    parts = re.split(r"(\d+)", s)
    key = []
    for part in parts:
        if part.isdigit():
            leading_zero_flag = 0 if part.startswith("0") and part != "0" else 1
            key.append((leading_zero_flag, int(part)))
        else:
            key.append((2, part.lower()))
    return key


def sort_naturally(array_: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    return sorted(array_, key=lambda x: natural_key(x[0]))


def load_sql_scripts_on_dir(dir_: str, pattern: str = "*.sql") -> List[Tuple[str, str]]:
    dir_path = pathlib.Path(dir_)
    file_contents = []

    for file in dir_path.glob(pattern):
        if file.is_file():
            content = file.read_text(encoding="utf-8")
            file_contents.append((file.name, content))

    return sort_naturally(file_contents)


def format_str(string: str, repl_pairs: List[Tuple[str, str]]) -> str:
    for pair in repl_pairs:
        string = string.replace(pair[0], pair[1])
    return string


class SQLApplyTool:
    MODES_MAP = \
        {
            "single-transaction": "-eX -1 -v ON_ERROR_STOP=on",
            "on-error-stop": "-eX -v ON_ERROR_STOP=on"
        }

    PSQL_EXIT_STATUSES = \
        {
            0: "SUCCESS",
            1: "PSQL_FATAL_ERROR",
            2: "CONNECTION_ERROR",
            3: "SCRIPT_ERROR"
        }

    BASE_CONFIIG = str(pathlib.Path(__file__).resolve().parent) + "/sql_apply.conf"

    def __init__(self, conf_file: str | None):
        self.conf = load_config(str(conf_file) if conf_file else self.BASE_CONFIIG)

        self._stop_executing_p: bool = False

        self.__setup_logging__()

    def __setup_logging__(self):
        os.makedirs(self.conf['DEFAULT']['logs_dir'], exist_ok=True)
        os.makedirs(self.conf['DEFAULT']['logs_dir'] + "/execution_logs", exist_ok=True)
        log_filename = f"{self.conf['DEFAULT']['logs_dir']}/log_{datetime.now().strftime('%Y-%m-%d')}.log"

        logging.basicConfig(
            level=getattr(importlib.import_module("logging"), self.conf["DEFAULT"]["logging_level"]),
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_filename, encoding="utf-8", mode="a"),
                logging.StreamHandler()
            ]
        )

    def _log_script_execution(self, script_name: str, chg_name: str, dbname: str, log: str):
        dff = format_str(repl_pairs=[("/", "_")], string=script_name)

        filename = f"{dbname}_{chg_name}_{dff}.log"
        logfile_full_path = self.conf['DEFAULT']['logs_dir'] + f"/execution_logs/{filename}"

        log = f"-- LOG OF {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{log}\n"

        file_lock = Lock()
        with file_lock:
            with open(file=logfile_full_path,
                mode="a", encoding="utf-8") as logfile:

                logfile.write(log)

        return logfile_full_path, filename

    def _get_db_conf(self, dbname: str, printing_not_found_err: bool = True) -> SectionProxy | dict[str, str | Any]:
        dbname = str(dbname)

        if self.conf.has_section(dbname):
            db_conf = self.conf[dbname]

            db_conf["host"] = db_conf.get("host", "localhost")
            db_conf["port"] = db_conf.get("port", "5432")
            db_conf["user"] = db_conf.get("user", "postgres")
            db_conf["password"] = db_conf.get("password", "")
            db_conf["dbname"] = db_conf.get("dbname", dbname)

            if not db_conf["port"].isdigit():
                logging.critical(f"(Database '{db_conf['dbname']}') Port must be an integer")
                sys.exit(1)

            return db_conf
        else:
            if printing_not_found_err:
                logging.warning(f"Record in config of db '{dbname}' not found, using UNIX socket")
            db_conf = {"host": "localhost", "port": "5432", "user": "postgres", "password": "", "dbname": dbname}
            return db_conf

    def _init_dbs_cli(self, args: Namespace):
        self.init_dbs(target_db=args.dbname, _change_name=args.change_name if args.change_name else None)

    def init_dbs(self, target_db: str, _change_name: str|None = None):
        if target_db == "ALL":
            if not _change_name:
                logging.critical(
                    "Usage '--init --dbname <dbname>' or '<change_name> --init' for init all databases usages by change"
                )
                sys.exit(1)

            path_to_change = self.conf["DEFAULT"]["changes_dir"] + f"/{_change_name}"

            logging.info(f"Initializing all databases used in change '{_change_name}'")

            if not os.path.exists(path_to_change):
                logging.critical(f"Change folder not found ({path_to_change})")
                sys.exit(1)

            with os.scandir(path_to_change) as entries:
                entries = list(entries)
                for entry in entries:
                    if entry.is_dir():
                        self._init_single_db(db_name=entry.name)
        else: self._init_single_db(db_name=target_db)

    def _init_single_db(self, db_name: str):
        db_conf = self._get_db_conf(dbname=db_name)
        self._check_db(db_conf=db_conf, checking_init=False)

        src = str(pathlib.Path(__file__).resolve().parent) + "/sql/init.sql"

        logging.info(f"Initialize database '{db_name}'")

        response = execute_sql_file(
            db_conf=db_conf,
            args=self.MODES_MAP["single-transaction"],
            src_path=src
        )

        init_notices_list = \
            [
                "Table sqlapply.sqlapply_history already exists.",
                "Sequence sqlapply.sqlapply_history_seq already exists.",
                "Schema sqlapply already exists."
            ]

        if response[2] != "":
            if all(notice in response[1] for notice in init_notices_list):
                logging.info(f"Database '{db_name}' already is initialized")

            [logging.error(err) for err in response[1].split("\n") if err != "" and err in init_notices_list]

    @staticmethod
    def _is_src_already_applied(db_conf: dict, change_name: str, script_file: str) -> int:
        sql = f"""
            SELECT status FROM sqlapply.sqlapply_history
            WHERE change_name = '{change_name}' AND script_file = '{script_file}'
            LIMIT 1;
        """
        response = execute_sql_string(db_conf=db_conf, args="-t -A", sql_request=sql)
        stdout, stderr, _, return_code = response[0], response[1], response[2], response[3]

        if return_code != 0 or not stdout.strip():
            return 0

        status = stdout.strip().upper()

        match status:
            case "SUCCESS": return 1
            case "IN_PROGRESS": return 3
            case "EXECUTION_STOPPED": return 4
            case _: return 2

    @staticmethod
    def _get_src_hash(db_conf: dict, script_name: str, chg_name: str) -> str | None:
        sql = f"""
            SELECT src_checksum FROM sqlapply.sqlapply_history
            WHERE change_name = '{chg_name}' AND script_file = '{script_name}'
            LIMIT 1;
        """
        response = execute_sql_string(db_conf=db_conf, args="-t -A", sql_request=sql)
        stdout, stderr, _, return_code = response

        if return_code != 0:
            logging.error(f"Failed to retrieve hash for {script_name} in change {chg_name}: {stderr}")
            return None
        if not stdout.strip():
            logging.debug(f"No hash found for {script_name} in change {chg_name}")
            return None

        return stdout.strip()

    def _show_change_cli(self, args: Namespace):
        if args.change_name: change_name = str(args.change_name)
        else:
            logging.critical("Usage '<change_name> --show'")
            sys.exit(1)

        path_to_change = self.conf["DEFAULT"]["changes_dir"] + f"/{change_name}"
        pattern = args.pattern if args.pattern else "*.sql"

        if not os.path.exists(path_to_change):
            logging.critical(f"Change folder not found ({path_to_change})")
            sys.exit(1)

        with os.scandir(path_to_change) as entries:
            entries = list(entries)

            root_node = CSNode(f"Change '{change_name}' (pattern: '{pattern}')", color="green")

            for entry in entries:
                if entry.is_dir():
                    dbname = entry.path.replace("\\", "/").split("/")[-1]
                    db_conf = self._get_db_conf(dbname=dbname, printing_not_found_err=False)
                    scripts = load_sql_scripts_on_dir(entry.path, pattern)

                    db_node = CSNode(f"DB '{dbname}' ({db_conf['host']}:{db_conf['port']})", color="cyan")

                    for src_name, _ in scripts:
                        db_node.add(CSNode(src_name))

                    root_node.add(db_node)

            tree = CSTree(root_node)
            tree.display()

    def _check_change_cli(self, args: Namespace):
        if args.change_name:
            change_name = str(args.change_name)
        else:
            logging.critical("Usage '<change_name> --check'")
            sys.exit(1)

        path_to_change = self.conf["DEFAULT"]["changes_dir"] + f"/{change_name}"
        pattern = args.pattern if args.pattern else "*.sql"
        force_mode = args.force if args.force else False
        exec_mode = args.mode if args.mode else "single-transaction"

        self.execute_change(
            exec_mode=exec_mode,
            pattern=pattern,
            change_name=change_name,
            path_to_change=path_to_change,
            force_mode=force_mode,
            check_change_=True
        )

    def _execute_change_cli(self, args: Namespace):
        change_name = str(args.change_name)
        path_to_change = self.conf["DEFAULT"]["changes_dir"] + f"/{change_name}"
        pattern = args.pattern if args.pattern else "*.sql"
        force_mode = args.force if args.force else False
        exec_mode = args.mode if args.mode else "single-transaction"

        self.execute_change(
            exec_mode=exec_mode,
            pattern=pattern,
            change_name=change_name,
            path_to_change=path_to_change,
            force_mode=force_mode
        )

    def execute_change(
            self, exec_mode: str, pattern: str, change_name: str, path_to_change: str,
            force_mode: str, check_change_=False
    ):
        if force_mode: force_mode = str(force_mode).lower()
        exec_mode_psql_args = self.MODES_MAP[str(exec_mode)]

        if not os.path.exists(path_to_change):
            logging.critical(f"Change folder not found ({path_to_change})")
            sys.exit(1)

        def stop_process_handler(_sig, _frame):
            logging.info("Process interruption by user")
            self._stop_executing_p = True

        signal.signal(signal.SIGINT, stop_process_handler)

        with os.scandir(path_to_change) as entries:
            for entry in list(entries):
                if not entry.is_dir(): continue
                dbname = entry.path.replace("\\", "/").split("/")[-1]
                self._check_db(db_conf=self._get_db_conf(dbname=dbname))

        logging.info(f"Finding files on pattern '{pattern}'...")

        with os.scandir(path_to_change) as entries:
            entries = list(entries)

            for entry in entries:
                if not entry.is_dir(): continue

                dbname = entry.path.replace("\\", "/").split("/")[-1]
                db_conf = self._get_db_conf(dbname=dbname, printing_not_found_err=False)
                scripts = load_sql_scripts_on_dir(entry.path, pattern)

                scripts_scheme = f"Executing scripts on db '{dbname}' (Total: {len(scripts)}):\n" + \
                                 "\n".join(f"- [ {i + 1}] {item[0]}" for i, item in enumerate(scripts))

                logging.debug(scripts_scheme)

                if self.conf["DEFAULT"]["logging_level"] != "DEBUG":
                    logging.info(f"Executing scripts on db '{dbname}' (Total: {len(scripts)})")

                for index, script in enumerate(scripts):
                    r = self._is_src_already_applied(
                        db_conf=db_conf, change_name=change_name, script_file=script[0]
                    )
                    scripts[index] += (r,)
                    if r not in [1, 2, 3, 4] and not check_change_:
                        self._insert_history_record(change_name=change_name, script=script, db_conf=db_conf)

                for script in scripts:
                    if self._stop_executing_p and not check_change_:
                        self._update_history_record(
                            change_name=change_name,
                            script=script,
                            exit_stat_str="EXECUTION_STOPPED",
                            db_conf=db_conf,
                            hash_=md5(script[1].encode("utf-8")).hexdigest()
                        )
                        continue

                    exec_setting = script[2]

                    _chm_err_src = False
                    _md5diff_flag_s2 = False
                    _is_new_exec = False
                    it_src_must_repeat_exec = False

                    src_hash = md5(script[1].encode("utf-8")).hexdigest()
                    last_src_hash = self._get_src_hash(db_conf=db_conf, chg_name=change_name, script_name=script[0])

                    if exec_setting == 1 and force_mode != "all":
                        logging.info(f"'{script[0]}' already applied, skipping")

                        if last_src_hash and last_src_hash != src_hash: _md5diff_flag_s2 = True
                        else: continue

                    if exec_setting == 1 and force_mode == "all":
                        it_src_must_repeat_exec = True

                    if exec_setting == 2 and force_mode not in ["all", "error"]:
                        msg = f"'{script[0]}' previously execute failed"
                        if not check_change_:
                            msg += " (lock '--help' with action 'force')"
                        logging.error(msg)
                        _chm_err_src = True
                        self._stop_executing_p = True

                    if exec_setting == 2 and force_mode in ["all", "error"]:
                        it_src_must_repeat_exec = True

                    if exec_setting == 3:
                        _log_str = f"Found record '{script[0]}' in history with status 'in progress'"
                        if not check_change_:
                            logging.error(_log_str)
                        else:
                            logging.warning(_log_str)

                    if exec_setting == 4 and force_mode in ["all", "error"]:
                        it_src_must_repeat_exec = True

                    if (not it_src_must_repeat_exec and not _chm_err_src and not _md5diff_flag_s2) or \
                       (not it_src_must_repeat_exec and exec_setting == 4 and not _md5diff_flag_s2):
                        _is_new_exec = True
                        if check_change_:
                            logging.info(f"'{script[0]}' new execution")

                    if _md5diff_flag_s2:
                        if force_mode != "md5diff":
                            logging.warning(
                                f"'{script[0]}' MD5 hash changed (" + \
                                f"previous: {last_src_hash[:6]}..., current: {src_hash[:6]}...)"
                            )
                        if force_mode == "md5diff": it_src_must_repeat_exec = True
                        else: continue

                    if check_change_:
                        if it_src_must_repeat_exec:
                            logging.info(f"'{script[0]}' will be executed again")
                        continue

                    if not _is_new_exec and not it_src_must_repeat_exec:
                        continue

                    ow_resp = execute_sql_file(
                        db_conf=db_conf,
                        args=exec_mode_psql_args,
                        src_path=f"{entry.path}/{script[0]}"
                    )

                    exit_stat_str = self.PSQL_EXIT_STATUSES[ow_resp[3]]

                    self._update_history_record(
                        change_name=change_name,
                        script=script,
                        exit_stat_str=exit_stat_str,
                        db_conf=db_conf,
                        hash_=src_hash
                    )

                    logfile_full_path, _ = self._log_script_execution(
                        script_name=script[0], chg_name=change_name, dbname=dbname, log=ow_resp[2]
                    )

                    if ow_resp[3] != 0:
                        logging.error(
                            f"Error of executing '{dbname}/{script[0]}' (lock src execution log)\n" + \
                            f"Execution log file: '{logfile_full_path}'"
                        )
                        self._stop_executing_p = True
                    else:
                        msg = f"'{script[0]}' successfully executed"
                        if it_src_must_repeat_exec:
                            msg += f" (forcing '{force_mode}')"
                        logging.info(msg)

                if not check_change_ and not self._stop_executing_p:
                    logging.info(f"Executing change in db '{db_conf['dbname']}' completed")
                if not check_change_ and self._stop_executing_p:
                    logging.error(f"Error executing change in db '{dbname}'")

            if not self._stop_executing_p:
                logging.info("Executing change completed")

    def _check_db(self, db_conf, db_name: str|None = None, checking_init: bool = True):
        sql = "SELECT * FROM sqlapply.sqlapply_history;"

        formated_sql = " ".join(sql.split()).strip()

        ow_resp_sys_r = execute_sql_string(
            db_conf=db_conf,
            args=self.MODES_MAP["single-transaction"],
            sql_request=formated_sql
        )

        not_init_err_str = "does not exist"
        connect_err_str = "psql: error: connection to server at"

        if ow_resp_sys_r[3] != 0:
            if connect_err_str in ow_resp_sys_r[2]:
                logging.critical(
                    f"Connection error of db '{db_name if db_name else db_conf['dbname']}'" + \
                    f" ({db_conf['host']}:{db_conf['port']})")
                sys.exit(1)

            if not checking_init: return
            if not_init_err_str in ow_resp_sys_r[2]:
                logging.critical(
                    f"Database '{db_conf['dbname']}' not initialized. (use '--init --dbname <dbname>' for init)")
                sys.exit(1)

    def _insert_history_record(self, change_name: str, script: Tuple, db_conf):
        insert_sql = open(file=self.conf["DEFAULT"]["core_dir"] + "/sql/insert_t.sql", mode="r").read()

        formated_insert_sql = " ".join(format_str(
            string=insert_sql,
            repl_pairs=[
                ("%change_name", change_name),
                ("%script_file", script[0]),
                ("%status", "IN_PROGRESS"),
                ("%src_checksum", md5(script[1].encode('utf-8')).hexdigest())
            ]
        ).split()).strip()

        ow_resp_sys_r = execute_sql_string(
            db_conf=db_conf,
            args=self.MODES_MAP["single-transaction"],
            sql_request=formated_insert_sql
        )

        if ow_resp_sys_r[3] != 0:
            logging.critical(
                f"Database '{db_conf['dbname']}' not initialized. (use '--init --dbname <dbname>' for init)"
            )
            sys.exit(1)

    def _update_history_record(self, change_name: str, script: Tuple, exit_stat_str: str, db_conf,
                               hash_: str):
        insert_sql = open(file=self.conf["DEFAULT"]["core_dir"] + "/sql/update_t.sql", mode="r").read()

        formated_insert_sql = " ".join(format_str(
            string=insert_sql,
            repl_pairs=[
                ("%change_name", change_name),
                ("%script_file", script[0]),
                ("%new_status", exit_stat_str),
                ("%new_hash", hash_)
            ]
        ).split()).strip()

        ow_resp_sys_r = execute_sql_string(
            db_conf=db_conf,
            args=self.MODES_MAP["single-transaction"],
            sql_request=formated_insert_sql
        )

        if ow_resp_sys_r[3] != 0:
            logging.critical(f"Error of executing sqlapply history insert script:\n{ow_resp_sys_r[2]}")
            sys.exit(1)

    def _exec_by_args(self, args: Namespace):
        args_map = \
            {
                "init": "_init_dbs_cli",
                "show": "_show_change_cli",
                "check": "_check_change_cli",
                "export-history": "_export_history_as_cvs",
            }

        for arg, handler in args_map.items():
            value = getattr(args, arg, None)
            if value:
                getattr(self, handler)(args=args)
                sys.exit(0)
        else:
            if args.change_name: self._execute_change_cli(args=args)

    def exec(self, args: Namespace): self._exec_by_args(args=args)
