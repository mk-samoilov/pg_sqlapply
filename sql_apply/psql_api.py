import subprocess
import shlex
import select

from urllib.parse import quote


def _execute_cl_command(cmd: str) -> tuple[str, str, str, int]:
    cmd_parts = shlex.split(cmd)

    process = subprocess.Popen(
        cmd_parts,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout_lines = []
    stderr_lines = []
    combined_lines = []

    while process.poll() is None:
        readable, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)

        for stream in readable:
            line = stream.readline().strip()
            if line:
                if stream == process.stdout:
                    stdout_lines.append(line)
                    combined_lines.append(line)
                elif stream == process.stderr:
                    stderr_lines.append(line)
                    combined_lines.append(line)

    stdout_remainder, stderr_remainder = process.communicate()

    if stdout_remainder:
        for line in stdout_remainder.strip().splitlines():
            stdout_lines.append(line)
            combined_lines.append(line)
    if stderr_remainder:
        for line in stderr_remainder.strip().splitlines():
            stderr_lines.append(line)
            combined_lines.append(line)

    return (
        "\n".join(stdout_lines),
        "\n".join(stderr_lines),
        "\n".join(combined_lines),
        process.returncode
    )


def gen_login_url(db_conf: dict) -> str:
    return f"postgresql://{quote(db_conf.get('username', 'postgres'))}" + \
        f"{':' + quote(db_conf['password']) if db_conf.get('password') else ''}" + \
        f"@{quote(db_conf['host'])}" + \
        f"{':' + db_conf['port'] if db_conf.get('port') else ''}/{quote(db_conf.get('dbname', ''))}"
    # postgresql://username:password@host:port/dbname


def execute_sql_string(db_conf: dict, args: str, sql_request: str):
    cmd = f'psql {gen_login_url(db_conf=db_conf)} {args} -c "{str(sql_request)}"'

    return _execute_cl_command(cmd=cmd)


def execute_sql_file(db_conf: dict, args: str, src_path: str):
    cmd = f"psql {gen_login_url(db_conf=db_conf)} {args} -f {str(src_path)}"
    return _execute_cl_command(cmd=cmd)
