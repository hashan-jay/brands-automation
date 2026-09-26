"""CUNTWIN brand API reader. Uses the access id and token from .env."""
from __future__ import annotations

import argparse
import json
from datetime import date

from src.client import CuntwinClient
from src.config import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Read CUNTWIN data with the brand API key")
    parser.add_argument(
        "action",
        choices=("ping", "member", "soccer"),
        help="ping checks the key, member looks up one player, soccer reads bet history",
    )
    parser.add_argument("--username", default="", help="Player username, with or without the access-id prefix")
    parser.add_argument("--date", default="", help="Soccer bet date YYYY-MM-DD, default today")
    args = parser.parse_args()
    settings = load_settings()
    settings.require()
    client = CuntwinClient(settings)
    username = args.username.strip()
    if username and "@" not in username:
        username = f"{settings.access_id}@{username}"

    if args.action == "ping":
        result = client.call("/member/get", username=f"{settings.access_id}@sample")
    elif args.action == "member":
        if not username:
            raise SystemExit("Pass --username for a member lookup")
        result = client.call("/member/get", username=username)
    else:
        bet_date = args.date.strip() or date.today().isoformat()
        result = client.call(
            "/soccer/getHistory",
            username=username,
            betDate=bet_date,
            pageSize="20",
            pageIndex="0",
        )
    print(json.dumps(result, indent=2, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
