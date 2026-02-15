from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ExecStatus(Enum):
    SUCCESS = "SUCCESS"
    PSQL_FATAL_ERROR = "PSQL_FATAL_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    SCRIPT_ERROR = "SCRIPT_ERROR"
    IN_PROGRESS = "IN_PROGRESS"
    EXECUTION_STOPPED = "EXECUTION_STOPPED"

    @classmethod
    def from_returncode(cls, code: int) -> "ExecStatus":
        return {
            0: cls.SUCCESS,
            1: cls.PSQL_FATAL_ERROR,
            2: cls.CONNECTION_ERROR,
            3: cls.SCRIPT_ERROR,
        }[code]


class ScriptState(Enum):
    NEW = 0
    APPLIED = 1
    FAILED = 2
    IN_PROGRESS = 3
    STOPPED = 4

    @classmethod
    def from_db_status(cls, status: str) -> "ScriptState":
        mapping = {
            "SUCCESS": cls.APPLIED,
            "IN_PROGRESS": cls.IN_PROGRESS,
            "EXECUTION_STOPPED": cls.STOPPED,
        }
        return mapping.get(status.upper(), cls.FAILED)


class ExecMode(Enum):
    SINGLE_TRANSACTION = "single-transaction"
    ON_ERROR_STOP = "on-error-stop"

    @property
    def psql_args(self) -> str:
        if self == ExecMode.SINGLE_TRANSACTION:
            return "-eX -1 -v ON_ERROR_STOP=on"
        return "-eX -v ON_ERROR_STOP=on"


class ForceMode(Enum):
    ALL = "all"
    ERROR = "error"
    MD5DIFF = "md5diff"


@dataclass
class PsqlResult:
    stdout: str
    stderr: str
    combined: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def status(self) -> ExecStatus:
        return ExecStatus.from_returncode(self.returncode)


@dataclass
class Script:
    name: str
    content: str
    path: Path
    state: ScriptState = field(default=ScriptState.NEW)
