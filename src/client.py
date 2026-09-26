from __future__ import annotations

from typing import Any

import requests

from src.config import Settings

READ_MODULES = {
    "member": "/member/get",
    "launch": "/member/getLaunchURL",
    "iframe": "/member/getIframeURL",
    "soccer": "/soccer/getHistory",
}


class CuntwinClient:
    def __init__(self, settings: Settings, timeout: float = 20) -> None:
        self.settings = settings
        self.timeout = timeout

    def call(self, module: str, **params: str) -> dict[str, Any]:
        data = {
            "module": module,
            "accessId": self.settings.access_id,
            "accessToken": self.settings.token,
        }
        for key, value in params.items():
            if value:
                data[key] = value
        try:
            response = requests.post(self.settings.api_url, data=data, timeout=self.timeout)
        except requests.RequestException as exc:
            return {"ok": False, "error": f"Could not reach {self.settings.api_url}: {exc.__class__.__name__}"}
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text[:300]}
        if not isinstance(body, dict):
            body = {"raw": body}
        body["http_status"] = response.status_code
        return body

    def soccer_pages(self, username: str = "", bet_date: str = "", pages: int = 5) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for index in range(pages):
            payload = self.call(
                "/soccer/getHistory",
                username=username,
                betDate=bet_date,
                pageSize="100",
                pageIndex=str(index),
            )
            found.append(payload)
            rows = _rows(payload)
            if payload.get("ok") is False or not rows or len(rows) < 100:
                break
        return found

    def gather(self, username: str = "", bet_date: str = "") -> dict[str, Any]:
        player = username.strip()
        if player and "@" not in player:
            player = f"{self.settings.access_id}@{player}"
        report: dict[str, Any] = {
            "access_id": self.settings.access_id,
            "api_url": self.settings.api_url,
            "whitelist_ip": self.settings.whitelist_ip,
            "iframe": self.call("/member/getIframeURL", lang="EN"),
            "soccer": self.soccer_pages(player, bet_date),
        }
        if player:
            report["member"] = self.call("/member/get", username=player)
            report["launch"] = self.call("/member/getLaunchURL", username=player, lang="EN")
        return report


def _rows(payload: dict[str, Any]) -> list:
    for key in ("data", "history", "rows", "list", "bets", "transactions", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []
