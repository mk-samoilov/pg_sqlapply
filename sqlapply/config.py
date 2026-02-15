import configparser
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DbConfig:
    dbname: str
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = ""


@dataclass
class Config:
    databases: dict[str, DbConfig] = field(default_factory=dict)
    logging_level: str = "INFO"
    core_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
    logs_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "logs")
    changes_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "changes")

    def get_db(self, name: str) -> DbConfig:
        if name in self.databases:
            return self.databases[name]
        logging.warning(f"Database '{name}' not found in config, using defaults (UNIX socket)")
        return DbConfig(dbname=name)


def load_config(config_path: str | None = None) -> Config:
    if config_path is None:
        config_path = str(Path(__file__).resolve().parent.parent / "sqlapply.conf")

    path = Path(config_path)
    parser = configparser.ConfigParser()

    if not path.exists():
        parser["DEFAULT"] = {
            "logging_level": "INFO",
            "core_dir": str(Path(__file__).resolve().parent),
            "logs_dir": str(Path(__file__).resolve().parent.parent / "logs"),
            "changes_dir": str(Path(__file__).resolve().parent.parent / "changes"),
        }
        parser["test_db"] = {
            "host": "localhost",
            "port": "5432",
            "user": "test_usr",
            "password": "test_usr",
            "dbname": "test_db",
        }
        try:
            with open(path, "w") as f:
                parser.write(f)
        except PermissionError:
            logging.critical(f"No permission to write config '{path}'")
            sys.exit(1)
        logging.info(f"Created config template: {path}")
        logging.info("Edit it and run again.")
        sys.exit(0)

    parser.read(path)

    defaults = parser["DEFAULT"]
    config = Config(
        logging_level=defaults.get("logging_level", "INFO"),
        core_dir=Path(defaults.get("core_dir", str(Path(__file__).resolve().parent))),
        logs_dir=Path(defaults.get("logs_dir", str(Path(__file__).resolve().parent.parent / "logs"))),
        changes_dir=Path(defaults.get("changes_dir", str(Path(__file__).resolve().parent.parent / "changes"))),
    )

    for section in parser.sections():
        sec = parser[section]
        port_str = sec.get("port", "5432")
        if not port_str.isdigit():
            logging.critical(f"(Database '{section}') Port must be an integer")
            sys.exit(1)

        config.databases[section] = DbConfig(
            dbname=sec.get("dbname", section),
            host=sec.get("host", "localhost"),
            port=int(port_str),
            user=sec.get("user", "postgres"),
            password=sec.get("password", ""),
        )

    return config
