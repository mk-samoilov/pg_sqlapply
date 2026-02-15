import argparse
import logging
import sys

from .config import load_config
from .core import SQLApplyTool
from .models import ExecMode, ForceMode
from .history import SQLApplyError


def main():
    parser = argparse.ArgumentParser(description="sqlapply — PostgreSQL migration tool")

    parser.add_argument("change_name", type=str, nargs="?", help="Change name")
    parser.add_argument("-i", "--init", action="store_true", help="Initialize sqlapply schema on target database")

    action = parser.add_mutually_exclusive_group()
    action.add_argument("-s", "--show", action="store_true", help="Show changeset structure")
    action.add_argument("-c", "--check", action="store_true", help="Dry-run: check what would be executed")

    parser.add_argument("--dbname", type=str, default="ALL", help="Target database (default: all in change)")
    parser.add_argument("-f", "--force", type=str, choices=["ALL", "ERROR", "MD5DIFF"], help="Force re-execution mode")
    parser.add_argument("-p", "--pattern", type=str, default="*.sql", help="Glob pattern for SQL files")
    parser.add_argument("-C", "--config", type=str, help="Path to config file")
    parser.add_argument(
        "-m", "--mode", type=str,
        choices=["single-transaction", "on-error-stop"],
        default="single-transaction",
        help="Execution mode (default: single-transaction)",
    )

    args = parser.parse_args()

    try:
        config = load_config(args.config)
        tool = SQLApplyTool(config)

        if args.init:
            tool.init_dbs(
                target_db=args.dbname,
                change_name=args.change_name,
            )
            return

        if not args.change_name:
            parser.print_help()
            return

        force = ForceMode(args.force.lower()) if args.force else None
        exec_mode = ExecMode(args.mode)

        if args.show:
            tool.show_change(args.change_name, args.pattern)
        elif args.check:
            tool.execute_change(
                change_name=args.change_name,
                exec_mode=exec_mode,
                pattern=args.pattern,
                force_mode=force,
                dry_run=True,
            )
        else:
            tool.execute_change(
                change_name=args.change_name,
                exec_mode=exec_mode,
                pattern=args.pattern,
                force_mode=force,
            )

    except SQLApplyError as e:
        logging.critical(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
