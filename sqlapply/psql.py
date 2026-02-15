import shlex
import select
import subprocess

from urllib.parse import quote

from .config import DbConfig
from .models import PsqlResult


def gen_login_url(db: DbConfig) -> str:
    if not db.host or db.host.lower() == "local":
        url = f"postgresql:///{quote(db.dbname)}"
        params = [f"user={quote(db.user)}"]
        if db.password:
            params.append(f"password={quote(db.password)}")
        return url + "?" + "&".join(params)

    url = f"postgresql://{quote(db.user)}"
    if db.password:
        url += f":{quote(db.password)}"
    url += f"@{quote(db.host)}:{db.port}/{quote(db.dbname)}"
    return url


def _run(cmd: str) -> PsqlResult:
    parts = shlex.split(cmd)
    proc = subprocess.Popen(
        parts,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    combined: list[str] = []

    while proc.poll() is None:
        readable, _, _ = select.select([proc.stdout, proc.stderr], [], [], 0.1)
        for stream in readable:
            line = stream.readline().strip()
            if line:
                bucket = stdout_lines if stream == proc.stdout else stderr_lines
                bucket.append(line)
                combined.append(line)

    rest_out, rest_err = proc.communicate()
    for line in (rest_out or "").strip().splitlines():
        stdout_lines.append(line)
        combined.append(line)
    for line in (rest_err or "").strip().splitlines():
        stderr_lines.append(line)
        combined.append(line)

    return PsqlResult(
        stdout="\n".join(stdout_lines),
        stderr="\n".join(stderr_lines),
        combined="\n".join(combined),
        returncode=proc.returncode,
    )


def exec_sql(db: DbConfig, sql: str, args: str = "") -> PsqlResult:
    cmd = f"psql {gen_login_url(db)} {args} -c \"{sql}\""
    return _run(cmd)


def exec_file(db: DbConfig, path: str, args: str = "") -> PsqlResult:
    cmd = f"psql {gen_login_url(db)} {args} -f {path}"
    return _run(cmd)
