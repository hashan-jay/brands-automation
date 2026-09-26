"""Load completed transactions from each brand domain."""
from __future__ import annotations

import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BRANDS = (
    {"name": "FF29", "domain": "https://ff29.co", "access_id": "451683474", "merchant_id": "30526"},
    {"name": "SPINOO", "domain": "https://spinoo.net", "access_id": "453733974", "merchant_id": "60732"},
    {"name": "COKESPIN", "domain": "https://cokespin.com", "access_id": "453734281", "merchant_id": "60733"},
    {"name": "BETCLUB6", "domain": "https://betclub6.net", "access_id": "453734333", "merchant_id": "60267"},
    {"name": "MATE29", "domain": "https://mate29.com", "access_id": "451683803", "merchant_id": "30527"},
    {"name": "CUNTWIN", "domain": "https://cuntwin.com", "access_id": "453687422", "merchant_id": "10364"},
)
_TAG_RE = re.compile(r"<span[^>]*>(.*?)</span>", re.I)
_HTML_RE = re.compile(r"<[^>]+>")


def load_tokens() -> dict[str, str]:
    path = ROOT / "brands.local.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(item["name"]): str(item["token"]) for item in data}


def fetch_brand(brand: dict, token: str, day: str) -> tuple[list[dict], str]:
    url = brand["domain"].rstrip("/") + "/api/v1/index.php"
    rows: list[dict] = []
    page = 0
    while page < 40:
        response = requests.post(
            url,
            data={
                "module": "/transactions/getAllTransactions",
                "accessId": brand["access_id"],
                "accessToken": token,
                "merchantId": brand["merchant_id"],
                "pageIndex": str(page),
                "status": "COMPLETED",
                "sDate": f"{day} 00:00:00",
                "eDate": f"{day} 23:59:59",
            },
            timeout=25,
        )
        body = response.json()
        if str(body.get("status") or "") != "SUCCESS":
            message = ""
            data = body.get("data")
            if isinstance(data, dict):
                message = str(data.get("message") or "")
            return rows, message or "The brand API refused the request"
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        batch = data.get("transactions") if isinstance(data.get("transactions"), list) else []
        rows.extend(item for item in batch if isinstance(item, dict))
        total_page = int(data.get("totalPage") or 1)
        if not batch or page + 1 >= total_page:
            break
        page += 1
    return rows, ""


def display_rows(raw_rows: list[dict], brand_name: str) -> list[dict[str, str]]:
    shown = []
    for raw in raw_rows:
        user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
        bank = _bank(user.get("bank"))
        tags = _TAG_RE.findall(str(user.get("name") or ""))
        brand = brand_name
        if tags:
            brand = brand_name + " · " + ", ".join(tags)
        shown.append(
            {
                "time": _clock(raw.get("createdDateTime")),
                "id": str(raw.get("id") or ""),
                "username": str(user.get("username") or ""),
                "name": str(user.get("originalName") or _HTML_RE.sub("", str(user.get("name") or ""))),
                "mobile": str(user.get("mobile") or ""),
                "amount": str(raw.get("cash") or ""),
                "type": str(raw.get("type") or ""),
                "bank": bank.get("bank", ""),
                "acc_name": bank.get("bankAccountName", ""),
                "acc_no": bank.get("bankAccountNumber", ""),
                "bsb": bank.get("bankBSB", ""),
                "pay_id": bank.get("payID", ""),
                "bank_lock": str(bank.get("bankLock") or ""),
                "method": _method(raw),
                "brand": brand,
                "created": _clock(raw.get("createdDateTime")),
                "processed": _clock(raw.get("processedDateTime")),
                "status": str(raw.get("status") or ""),
                "detail": _detail(raw),
            }
        )
    return shown


def _bank(value: object) -> dict:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _clock(value: object) -> str:
    text = str(value or "").replace("T", " ")
    return text[:16]


def _method(raw: dict) -> str:
    details = raw.get("details")
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            return ""
    if isinstance(details, dict):
        return str(details.get("method") or "")
    return ""


def _detail(raw: dict) -> str:
    promotion = raw.get("promotion")
    if isinstance(promotion, dict) and promotion.get("name"):
        return str(promotion["name"])
    return _method(raw)
