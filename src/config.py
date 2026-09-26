from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    access_id: str
    token: str
    api_url: str
    whitelist_ip: str

    def require(self) -> None:
        missing = []
        if not self.access_id:
            missing.append("CUNTWIN_ACCESS_ID")
        if not self.token:
            missing.append("CUNTWIN_TOKEN")
        if not self.api_url:
            missing.append("CUNTWIN_API_URL")
        if missing:
            raise SystemExit("Missing " + ", ".join(missing) + " in .env")


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    return Settings(
        access_id=os.getenv("CUNTWIN_ACCESS_ID", "").strip(),
        token=os.getenv("CUNTWIN_TOKEN", "").strip(),
        api_url=os.getenv(
            "CUNTWIN_API_URL", "https://a1.gwvkyk.com/api/v1/index.php"
        ).strip(),
        whitelist_ip=os.getenv("CUNTWIN_WHITELIST_IP", "81.180.120.241").strip(),
    )
