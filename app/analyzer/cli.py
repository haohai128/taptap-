from __future__ import annotations

import argparse
import logging
import sys

from app.core.config import load_config
from app.core.db import init_engine, get_engine
from app.analyzer.analyzer import SinglePostAnalyzer
from app.analyzer.client import build_openai_client
from app.analyzer.service import analyze_post, fetch_pending_posts
from sqlmodel import Session


def run_analyze_now(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO)
    config = load_config(args.config, require_ai=True)
    init_engine(config)
    from app.core.db import create_all
    create_all()
    client = build_openai_client(config.ai)
    analyzer = SinglePostAnalyzer(client, config.ai.model, use_json_mode=True)

    with Session(get_engine()) as session:
        posts = fetch_pending_posts(session, args.community, batch_size=config.analyzer.batch_size)
        ok = 0
        for p in posts:
            success = analyze_post(session, p, analyzer, max_attempts=config.analyzer.max_attempts)
            if success:
                ok += 1
        print(f"分析完成: 共 {len(posts)} 帖, 成功 {ok}, 失败 {len(posts) - ok}")
    return 0
