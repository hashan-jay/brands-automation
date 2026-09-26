"""Brand transaction window, laid out like the finance list."""
from __future__ import annotations

import threading
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk

from src.transactions import BRANDS, LIVE_STATUSES, display_rows, fetch_brand, load_tokens

COLUMNS = (
    "time",
    "id",
    "username",
    "name",
    "mobile",
    "amount",
    "type",
    "bank",
    "acc_name",
    "acc_no",
    "bsb",
    "pay_id",
    "brand",
    "created",
    "processed",
    "status",
    "detail",
)
HEADINGS = {
    "time": ("Time", 130),
    "id": ("ID", 130),
    "username": ("Username", 110),
    "name": ("Name", 170),
    "mobile": ("Mobile", 110),
    "amount": ("Amount", 80),
    "type": ("Type", 90),
    "bank": ("Bank", 90),
    "acc_name": ("Acc Name", 160),
    "acc_no": ("Acc No", 120),
    "bsb": ("BSB", 80),
    "pay_id": ("PayID", 140),
    "brand": ("Brand", 160),
    "created": ("Created", 130),
    "processed": ("Processed", 130),
    "status": ("Status", 100),
    "detail": ("Detail", 180),
}
TYPE_COLOR = {
    "DEPOSIT": "#15803d",
    "WITHDRAW": "#b91c1c",
    "BONUS": "#1d4ed8",
    "PENDING": "#a16207",
    "REJECTED": "#6b7280",
}


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Brand transactions")
        self.geometry("1280x760")
        self.minsize(980, 560)
        self.configure(bg="#eef2f7")
        self._rows: list[dict[str, str]] = []
        self._cache: dict[tuple[str, str], dict] = {}
        self._busy = False
        self._closed = False
        self._signature = ()
        self._brand_vars = {item["name"]: tk.BooleanVar(value=True) for item in BRANDS}
        self._date = tk.StringVar(value=date.today().isoformat())
        self._status = tk.StringVar(value="Connecting to the brand APIs.")
        self._tally = tk.StringVar(value="Waiting for the first API response.")
        self._style()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(300, self._kick)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Root.TFrame", background="#eef2f7")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#0f2744", font=("Segoe UI", 12, "bold"))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#5b6b7c", font=("Segoe UI", 9))
        style.configure("Side.TLabel", background="#ffffff", foreground="#0f2744", font=("Segoe UI", 10))
        style.configure("Tally.TLabel", background="#f4f7fb", foreground="#0f2744", font=("Segoe UI", 10))
        style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", foreground="#0f172a", rowheight=24, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#e2e8f0", foreground="#0f2744", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#bfdbfe")])
        style.configure("Run.TButton", background="#0f766e", foreground="#f0fdfa", font=("Segoe UI", 10, "bold"))

    def _build(self) -> None:
        header = tk.Frame(self, bg="#0f2744", height=64)
        header.pack(fill="x")
        tk.Label(header, text="Brand transactions", bg="#0f2744", fg="#ffffff", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=16, pady=(10, 0))
        tk.Label(header, text="Live API rows, refreshed every second", bg="#0f2744", fg="#c5d4e8", font=("Segoe UI", 9)).pack(anchor="w", padx=16)

        body = ttk.Frame(self, style="Root.TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        side = ttk.Frame(body, style="Card.TFrame", padding=12)
        side.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        ttk.Label(side, text="Brands", style="CardTitle.TLabel").pack(anchor="w")
        for item in BRANDS:
            ttk.Checkbutton(side, text=item["name"], variable=self._brand_vars[item["name"]]).pack(anchor="w", pady=2)
        ttk.Label(side, text="Date", style="CardTitle.TLabel").pack(anchor="w", pady=(14, 4))
        ttk.Entry(side, textvariable=self._date, width=18).pack(anchor="w")
        ttk.Button(side, text="Refresh now", style="Run.TButton", command=self._kick).pack(anchor="w", pady=(14, 6))
        ttk.Label(side, textvariable=self._status, style="Muted.TLabel", wraplength=180).pack(anchor="w")

        main = ttk.Frame(body, style="Card.TFrame", padding=12)
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)
        bar = ttk.Frame(main, style="Card.TFrame")
        bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, text="Transactions", style="CardTitle.TLabel").pack(side="left")
        self._type = tk.StringVar(value="All types")
        self._view = tk.StringVar(value="All statuses")
        type_combo = ttk.Combobox(bar, textvariable=self._type, state="readonly", width=14, values=("All types", "DEPOSIT", "WITHDRAW", "BONUS"))
        type_combo.pack(side="right")
        type_combo.bind("<<ComboboxSelected>>", lambda _event: self._fill(force=True))
        ttk.Label(bar, text="Type", style="Muted.TLabel").pack(side="right", padx=(8, 6))
        view_combo = ttk.Combobox(bar, textvariable=self._view, state="readonly", width=14, values=("All statuses", "PENDING", "COMPLETED", "REJECTED"))
        view_combo.pack(side="right")
        view_combo.bind("<<ComboboxSelected>>", lambda _event: self._fill(force=True))
        ttk.Label(bar, text="Status", style="Muted.TLabel").pack(side="right", padx=(0, 6))

        tree_wrap = ttk.Frame(main, style="Card.TFrame")
        tree_wrap.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_wrap, columns=COLUMNS, show="headings", selectmode="browse")
        for key, (label, width) in HEADINGS.items():
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=60, stretch=False)
        for kind, color in TYPE_COLOR.items():
            self.tree.tag_configure(kind, foreground=color)
        yscroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(tree_wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        tally = tk.Frame(main, bg="#f4f7fb")
        tally.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        tk.Label(tally, textvariable=self._tally, bg="#f4f7fb", fg="#0f2744", font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=8)

    def _close(self) -> None:
        self._closed = True
        self.destroy()

    def _kick(self) -> None:
        if self._closed or self._busy:
            return
        selected = [item for item in BRANDS if self._brand_vars[item["name"]].get()]
        day = self._date.get().strip()
        if not selected or not day:
            self._status.set("Select a brand and a date. The live poll is waiting.")
            self.after(1000, self._kick)
            return
        self._busy = True
        threading.Thread(target=self._poll, args=(selected, day), daemon=True).start()

    def _poll(self, selected: list[dict], day: str) -> None:
        try:
            tokens = load_tokens()
        except Exception as exc:
            self.after(0, lambda: self._finish([], [str(exc)]))
            return
        collected: list[dict] = []
        errors: list[str] = []
        for brand in selected:
            token = tokens.get(brand["name"], "")
            if not token:
                errors.append(brand["name"] + " has no token")
                continue
            for status in LIVE_STATUSES:
                raw, error = self._read_status(brand, token, day, status)
                if error:
                    errors.append(f"{brand['name']} {status}: {error}")
                collected.extend(raw)
        rows = []
        for brand in selected:
            brand_rows = [item for item in collected if item.get("_brand") == brand["name"]]
            rows.extend(display_rows(brand_rows, brand["name"]))
        self.after(0, lambda: self._finish(rows, errors))

    def _read_status(self, brand: dict, token: str, day: str, status: str) -> tuple[list[dict], str]:
        key = (brand["name"], status, day)
        try:
            if status == "PENDING":
                raw, error, total = fetch_brand(brand, token, day, status, max_pages=10)
                if not error:
                    self._cache[key] = {"sig": (total, ""), "raw": raw}
            else:
                raw, error, total = fetch_brand(brand, token, day, status, max_pages=1)
                head = str(raw[0].get("id") or "") if raw else ""
                cached = self._cache.get(key)
                if not error and cached and cached["sig"] == (total, head):
                    raw = cached["raw"]
                elif not error and total > len(raw):
                    raw, error, total = fetch_brand(brand, token, day, status, max_pages=40)
                    head = str(raw[0].get("id") or "") if raw else ""
                if not error:
                    self._cache[key] = {"sig": (total, head), "raw": raw}
        except Exception as exc:
            error = exc.__class__.__name__
            raw = []
        if error and key in self._cache:
            raw = self._cache[key]["raw"]
        for item in raw:
            item["_brand"] = brand["name"]
        return raw, error

    def _finish(self, rows: list[dict[str, str]], errors: list[str]) -> None:
        self._busy = False
        if self._closed:
            return
        self._rows = rows
        stamp = datetime.now().strftime("%H:%M:%S")
        if errors and not rows:
            self._status.set(stamp + "  " + " ".join(errors[:3]))
        elif errors:
            self._status.set(f"{stamp}  {len(rows)} API rows. " + " ".join(errors[:2]))
        else:
            self._status.set(f"{stamp}  {len(rows)} API rows.")
        self._fill()
        self.after(1000, self._kick)

    def _fill(self, force: bool = False) -> None:
        wanted_type = self._type.get()
        wanted_status = self._view.get()
        visible = []
        for row in self._rows:
            if wanted_type != "All types" and row["type"] != wanted_type:
                continue
            if wanted_status != "All statuses" and row["status"] != wanted_status:
                continue
            visible.append(row)
        signature = tuple((row["id"], row["status"], row["amount"], row["type"]) for row in visible)
        if signature != self._signature or force:
            self._signature = signature
            self.tree.delete(*self.tree.get_children())
            for row in visible:
                tag = row["status"] if row["status"] in {"PENDING", "REJECTED"} else row["type"]
                self.tree.insert("", "end", values=tuple(row[key] for key in COLUMNS), tags=(tag,))
        self._tally.set(_analytics(self._rows))


def _money(rows: list[dict[str, str]], **match: str) -> tuple[int, float]:
    chosen = []
    for row in rows:
        if all(row.get(key) == value for key, value in match.items()):
            chosen.append(row)
    amount = 0.0
    for row in chosen:
        try:
            amount += float(row["amount"] or 0)
        except ValueError:
            pass
    return len(chosen), amount


def _analytics(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "The API returned no rows for this date."
    pending_n, pending_amt = _money(rows, status="PENDING")
    done_n, done_amt = _money(rows, status="COMPLETED")
    rejected_n, _rejected_amt = _money(rows, status="REJECTED")
    deposit_n, deposit_amt = _money(rows, type="DEPOSIT")
    withdraw_n, withdraw_amt = _money(rows, type="WITHDRAW")
    brands = []
    for name in dict.fromkeys(row["brand"] for row in rows):
        brand_rows = [row for row in rows if row["brand"] == name]
        pending = sum(1 for row in brand_rows if row["status"] == "PENDING")
        brands.append(f"{name} {len(brand_rows)} ({pending} pending)")
    return (
        f"Pending {pending_n} · {pending_amt:,.2f}    "
        f"Completed {done_n} · {done_amt:,.2f}    "
        f"Rejected {rejected_n}    "
        f"Deposit {deposit_n} · {deposit_amt:,.2f}    "
        f"Withdraw {withdraw_n} · {withdraw_amt:,.2f}    "
        + "   ".join(brands)
    )


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
