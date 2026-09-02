from __future__ import annotations

import argparse
import sys
from typing import Sequence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app",
        description="TapTap Community Sentiment Analysis",
    )
    sub = parser.add_subparsers(dest="command")

    serve_parser = sub.add_parser("serve", help="启动 Web 服务（建库 + 迁移 + 调度器 + 分析消费者 + Dashboard）")

    collect_parser = sub.add_parser("collect-now", help="立即对指定社区执行一次采集")
    collect_parser.add_argument("--community", type=int, required=True, help="社区 ID")
    collect_parser.add_argument("--config", default="config.yaml")

    analyze_parser = sub.add_parser("analyze-now", help="立即对指定社区/时间范围执行一次分析")
    analyze_parser.add_argument("--community", type=int, default=None, help="社区 ID（不指定则处理全部待分析）")
    analyze_parser.add_argument("--config", default="config.yaml")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "serve":
        from app.dashboard.server import run_server

        run_server()
        return 0

    if args.command == "collect-now":
        from app.collector.cli import run_collect_now

        return run_collect_now(args)

    if args.command == "analyze-now":
        from app.analyzer.cli import run_analyze_now

        return run_analyze_now(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
