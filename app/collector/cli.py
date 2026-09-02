from __future__ import annotations

import argparse
import logging

import httpx

from app.core.config import load_config
from app.core.db import init_engine, get_engine
from app.collector.rate_limit import RateLimiter
from app.collector.service import run_collection
from app.collector.taptap_adapter import TapTapAdapter
from app.core.models import Community
from sqlmodel import Session, select


def run_collect_now(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO)
    config = load_config(args.config, require_ai=False)
    init_engine(config)
    from app.core.db import create_all
    create_all()
    adapter = TapTapAdapter(httpx.Client())
    rl = RateLimiter(min_interval_seconds=config.collector.min_request_interval_seconds)

    with Session(get_engine()) as session:
        community = session.get(Community, args.community)
        if not community:
            print(f"社区 {args.community} 不存在")
            return 1
        run = run_collection(session, community, adapter, rl, max_retries=config.collector.max_retries)
        print(f"采集完成: status={run.status} fetched={run.fetched_count} new={run.new_count} failed={run.failed_count}")
    return 0
