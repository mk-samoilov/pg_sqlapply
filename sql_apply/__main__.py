import argparse

from .core import SQLApplyTool


def starter():
    parser = argparse.ArgumentParser(description="Tool for changes (commits) in postgres databases")

    parser.add_argument(
        "change_name",
        type=str,
        nargs="?",
        help="Change name"
    )

    parser.add_argument(
        "-i", "--init",
        action="store_true",
        help="Initialize database (for working tool on target db)"
    )

    show_check_group = parser.add_mutually_exclusive_group()
    show_check_group.add_argument(
        "-s", "--show",
        action="store_true",
        help="Show change scripts (on scheme)"
    )
    show_check_group.add_argument(
        "-c", "--check",
        action="store_true",
        help="Check executing (e.g. to make sure before rolling out a release, etc.)"
    )

    parser.add_argument(
        "--dbname",
        type=str,
        default="ALL",
        help="Database name (default: All databases in change)"
    )

    parser.add_argument(
        "-f", "--force",
        type=str,
        choices=["ALL", "ERROR", "MD5DIFF"],
        help="Force execution: ALL, ERROR, or MD5DIFF"
    )

    parser.add_argument(
        "-p", "--pattern",
        type=str,
        default="*.sql",
        help="Set pattern for finding change scripts"
    )

    parser.add_argument(
        "-C", "--config",
        type=str,
        help="Specify path to config file"
    )

    parser.add_argument(
        "-m", "--mode",
        type=str,
        choices=["single-transaction", "on-error-stop"],
        default="single-transaction",
        help="Set executing mode (default: single-transaction)"
    )

    args = parser.parse_args()

    repl = SQLApplyTool(conf_file=args.config if args.config else None)
    repl.exec(args=args)


if __name__ == "__main__":
    starter()
