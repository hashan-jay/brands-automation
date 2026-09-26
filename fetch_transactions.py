"""Fetch each brand's transaction list from that brand's own domain."""
from __future__ import annotations

import json
from pathlib import Path

import requests

BRANDS = [
    ("FF29", "https://ff29.co", "451683474", "30526"),
    ("SPINOO", "https://spinoo.net", "453733974", "60732"),
    ("COKESPIN", "https://cokespin.com", "453734281", "60733"),
    ("BETCLUB6", "https://betclub6.net", "453734333", "60267"),
    ("MATE29", "https://mate29.com", "451683803", "30527"),
    ("CUNTWIN", "https://cuntwin.com", "453687422", "10364"),
]
KEYS = {
    item["name"]: item["token"]
    for item in json.loads(Path("brands.local.json").read_text(encoding="utf-8"))
}


def summarize(body: object, token: str) -> str:
    if not isinstance(body, dict):
        return str(body)[:160].replace(token, "***")
    status = str(body.get("status") or "")
    data = body.get("data")
    if isinstance(data, dict):
        note = str(data.get("message") or "")
        rows = data.get("transactions")
        count = data.get("totalCount")
        if isinstance(rows, list):
            return f"{status} rows={len(rows)} totalCount={count} {note}".strip()
        return f"{status} {note}".strip() or status
    text = json.dumps(body, ensure_ascii=False).replace(token, "***")
    return text[:180]


def fetch_page(url: str, form: dict, token: str) -> dict:
    response = requests.post(url, data=form, timeout=25)
    body = response.json()
    print(form["pageIndex"], response.status_code, summarize(body, token), flush=True)
    return body if isinstance(body, dict) else {}


def main() -> None:
    out = []
    for name, origin, access_id, merchant_id in BRANDS:
        token = KEYS[name]
        url = origin.rstrip("/") + "/api/v1/index.php"
        print("calling", name, url, flush=True)
        rows = []
        total = None
        status = ""
        try:
            for page in range(40):
                form = {
                    "module": "/transactions/getAllTransactions",
                    "accessId": access_id,
                    "accessToken": token,
                    "merchantId": merchant_id,
                    "pageIndex": str(page),
                    "status": "COMPLETED",
                    "sDate": "2026-09-26 00:00:00",
                    "eDate": "2026-09-26 23:59:59",
                }
                body = fetch_page(url, form, token)
                data = body.get("data") if isinstance(body.get("data"), dict) else {}
                status = str(body.get("status") or "")
                total = data.get("totalCount")
                batch = data.get("transactions") if isinstance(data.get("transactions"), list) else []
                if status != "SUCCESS" or not batch:
                    break
                rows.extend(batch)
                total_page = int(data.get("totalPage") or 1)
                if page + 1 >= total_page or len(rows) >= int(total or len(rows)):
                    break
        except requests.RequestException as exc:
            print(name, exc.__class__.__name__, flush=True)
            out.append({"brand": name, "error": exc.__class__.__name__, "rows": rows})
            continue
        print(name, "saved", len(rows), "of", total, flush=True)
        out.append(
            {
                "brand": name,
                "domain": origin,
                "status": status,
                "totalCount": total,
                "rows": rows,
            }
        )
    Path("data").mkdir(exist_ok=True)
    Path("data/transactions.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
