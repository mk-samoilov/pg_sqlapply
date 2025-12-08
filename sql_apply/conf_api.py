import logging
import sys
import configparser
import os

from pathlib import Path


def load_config(config_path="config.ini"):
    config = configparser.ConfigParser()

    if not os.path.exists(config_path):
        config["DEFAULT"] = {
            "logging_level": "INFO",
            "core_dir": str(Path(__file__).resolve().parent),
            "logs_dir": str(Path(__file__).resolve().parent.parent) + "/logs",
            "changes_dir": str(Path(__file__).resolve().parent.parent) + "/changes"
        }

        config["example_database"] = {
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "",
            "dbname": ""
        }

        try:
            with open(config_path, "w") as configfile:
                config.write(fp=configfile) # type: ignore
        except PermissionError:
            logging.critical(f"Have not permissions for write config file '{config_path}'")
            sys.exit(1)
    else: 
        config.read(config_path)

    return config
