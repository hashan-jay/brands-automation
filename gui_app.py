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
        self.geometry("1280x840")
        self.minsize(980, 560)
        self.configure(bg="#eef2f7")
        self._rows: list[dict[str, str]] = []
        self._cache: dict[tuple[str, str], dict] = {}
        self._pending_ids: dict[str, set[str]] = {}
        self._busy = False
        self._closed = False
        self._live = True
        self._generation = 0
        self._signature = ()
        self._brand = tk.StringVar(value="All")
        self._date = tk.StringVar(value=date.today().isoformat())
        self._status = tk.StringVar(value="Live updates are on. Connecting to the brand APIs.")
        self._stats = {
            key: tk.StringVar(value="—")
            for key in (
                "pending_deposit",
                "pending_withdraw",
                "completed_deposit",
                "completed_withdraw",
            )
        }
        self._brand_line = tk.StringVar(value="Waiting for the first API response.")
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
        style.configure("LiveOn.TButton", background="#0f766e", foreground="#f0fdfa", font=("Segoe UI", 10, "bold"))
        style.configure("LiveOff.TButton", background="#94a3b8", foreground="#0f172a", font=("Segoe UI", 10, "bold"))
        style.configure("Stat.TFrame", background="#f4f7fb")
        style.configure("StatTitle.TLabel", background="#f4f7fb", foreground="#5b6b7c", font=("Segoe UI", 8))
        style.configure("StatValue.TLabel", background="#f4f7fb", foreground="#0f2744", font=("Segoe UI", 12, "bold"))

    def _build(self) -> None:
        header = tk.Frame(self, bg="#0f2744", height=64)
        header.pack(fill="x")
        tk.Label(header, text="Brand transactions", bg="#0f2744", fg="#ffffff", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=16, pady=(10, 0))
        tk.Label(header, text="Live API rows. Turn Live on to refresh every second.", bg="#0f2744", fg="#c5d4e8", font=("Segoe UI", 9)).pack(anchor="w", padx=16)

        body = ttk.Frame(self, style="Root.TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        side = ttk.Frame(body, style="Card.TFrame", padding=12)
        side.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        ttk.Label(side, text="Brand", style="CardTitle.TLabel").pack(anchor="w")
        brand_names = ("All",) + tuple(item["name"] for item in BRANDS)
        brand_combo = ttk.Combobox(side, textvariable=self._brand, state="readonly", width=16, values=brand_names)
        brand_combo.pack(anchor="w", pady=(4, 0))
        brand_combo.bind("<<ComboboxSelected>>", self._on_brand_changed)
        ttk.Label(side, text="Date", style="CardTitle.TLabel").pack(anchor="w", pady=(14, 4))
        ttk.Entry(side, textvariable=self._date, width=18).pack(anchor="w")
        self._live_btn = tk.Button(
            side,
            text="Live: ON",
            command=self._toggle_live,
            bg="#0f766e",
            fg="#f0fdfa",
            activebackground="#115e59",
            activeforeground="#f0fdfa",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=4,
        )
        self._live_btn.pack(anchor="w", pady=(14, 6))
        ttk.Button(side, text="Refresh now", style="Run.TButton", command=self._refresh_now).pack(anchor="w")
        ttk.Label(side, textvariable=self._status, style="Muted.TLabel", wraplength=180).pack(anchor="w", pady=(10, 0))

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

        self._stats_title = tk.StringVar(value="Statistics")
        dash = tk.Frame(main, bg="#f4f7fb")
        dash.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        tk.Label(dash, textvariable=self._stats_title, bg="#f4f7fb", fg="#0f2744", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(8, 4))
        cards = (
            ("pending_deposit", "Pending deposits"),
            ("pending_withdraw", "Pending withdrawals"),
            ("completed_deposit", "Completed deposits"),
            ("completed_withdraw", "Completed withdrawals"),
        )
        for index, (key, title) in enumerate(cards):
            var = self._stats[key]
            card = tk.Frame(dash, bg="#ffffff", highlightbackground="#d6dee8", highlightthickness=1)
            card.grid(row=1, column=index, sticky="nsew", padx=8, pady=(0, 8))
            dash.columnconfigure(index, weight=1)
            tk.Label(card, text=title, bg="#ffffff", fg="#5b6b7c", font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, textvariable=var, bg="#ffffff", fg="#0f2744", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=8, pady=(0, 6))
        tk.Label(dash, textvariable=self._brand_line, bg="#f4f7fb", fg="#0f2744", font=("Segoe UI", 9), wraplength=980, justify="left").grid(row=2, column=0, columnspan=4, sticky="w", padx=10, pady=(0, 8))

    def _close(self) -> None:
        self._closed = True
        self.destroy()

    def _toggle_live(self) -> None:
        self._live = not self._live
        if self._live:
            self._live_btn.configure(text="Live: ON", bg="#0f766e", fg="#f0fdfa")
        else:
            self._live_btn.configure(text="Live: OFF", bg="#94a3b8", fg="#0f172a")
        if self._live:
            self._status.set("Live is on. Updating from the APIs every second.")
            self._kick()
        else:
            self._status.set("Live is off. The list stays on the last API response.")

    def _on_brand_changed(self, _event: object = None) -> None:
        self._signature = ()
        self._fill(force=True)
        if self._live:
            self._kick()

    def _refresh_now(self) -> None:
        self._kick(force=True)

    def _kick(self, force: bool = False) -> None:
        if self._closed or self._busy:
            return
        if not self._live and not force:
            return
        selected = self._selected_brands()
        day = self._date.get().strip()
        if not selected or not day:
            self._status.set("Choose a date. Live is waiting.")
            if self._live:
                self.after(1000, self._kick)
            return
        self._busy = True
        threading.Thread(target=self._poll, args=(selected, day), daemon=True).start()

    def _selected_brands(self) -> list[dict]:
        name = self._brand.get()
        if name == "All":
            return list(BRANDS)
        return [item for item in BRANDS if item["name"] == name]

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
            pending_key = (brand["name"], "PENDING", day)
            previous_ids = _ids(self._cache.get(pending_key, {}).get("raw", []))
            pending_raw, pending_error = self._read_status(brand, token, day, "PENDING", force_full=True)
            if pending_error:
                errors.append(f"{brand['name']} PENDING: {pending_error}")
            collected.extend(pending_raw)
            pending_changed = previous_ids != _ids(pending_raw)
            for status in ("COMPLETED", "REJECTED"):
                raw, error = self._read_status(brand, token, day, status, force_full=pending_changed)
                if error:
                    errors.append(f"{brand['name']} {status}: {error}")
                collected.extend(raw)
        rows = []
        for brand in selected:
            brand_rows = [item for item in collected if item.get("_brand") == brand["name"]]
            rows.extend(display_rows(brand_rows, brand["name"]))
        self.after(0, lambda: self._finish(rows, errors))

    def _read_status(self, brand: dict, token: str, day: str, status: str, force_full: bool = False) -> tuple[list[dict], str]:
        key = (brand["name"], status, day)
        try:
            if status == "PENDING":
                raw, error, total = fetch_brand(brand, token, day, status, max_pages=10)
                head = ""
                if not error:
                    self._cache[key] = {"sig": (total, head), "raw": raw}
            else:
                raw, error, total = fetch_brand(brand, token, day, status, max_pages=1)
                head = str(raw[0].get("id") or "") if raw else ""
                cached = self._cache.get(key)
                unchanged = cached and cached["sig"] == (total, head) and total <= len(cached["raw"])
                if not error and not force_full and unchanged:
                    raw = cached["raw"]
                elif not error and (force_full or total > len(raw)):
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
            state = "Live" if self._live else "Live is off"
            self._status.set(f"{state} {stamp}  ·  {len(rows)} API rows.")
        self._fill()
        if self._live:
            self.after(1000, self._kick)

    def _scoped_rows(self) -> list[dict[str, str]]:
        name = self._brand.get()
        if name == "All":
            return list(self._rows)
        return [row for row in self._rows if row["brand"] == name]

    def _fill(self, force: bool = False) -> None:
        scoped = self._scoped_rows()
        wanted_type = self._type.get()
        wanted_status = self._view.get()
        visible = []
        for row in scoped:
            if wanted_type != "All types" and row["type"] != wanted_type:
                continue
            if wanted_status != "All statuses" and row["status"] != wanted_status:
                continue
            visible.append(row)
        visible.sort(key=lambda row: row["time"], reverse=True)
        visible.sort(key=lambda row: row["status"] != "PENDING")
        signature = tuple((row["id"], row["status"], row["amount"], row["type"], row["brand"]) for row in visible)
        if signature != self._signature or force:
            self._signature = signature
            self.tree.delete(*self.tree.get_children())
            for row in visible:
                tag = row["status"] if row["status"] in {"PENDING", "REJECTED"} else row["type"]
                self.tree.insert("", "end", values=tuple(row[key] for key in COLUMNS), tags=(tag,))
        self._paint_stats(scoped)

    def _paint_stats(self, rows: list[dict[str, str]]) -> None:
        brand = self._brand.get() or "All"
        self._stats_title.set(f"Statistics  ·  {brand}")
        pairs = (
            ("pending_deposit", "PENDING", "DEPOSIT"),
            ("pending_withdraw", "PENDING", "WITHDRAW"),
            ("completed_deposit", "COMPLETED", "DEPOSIT"),
            ("completed_withdraw", "COMPLETED", "WITHDRAW"),
        )
        for key, status, kind in pairs:
            count, amount = _money(rows, status=status, type=kind)
            self._stats[key].set(f"{count}   ·   {amount:,.2f}")
        if not rows:
            self._brand_line.set(f"{brand}: the API returned no rows for this date.")
            return
        parts = []
        names = [brand] if brand != "All" else list(dict.fromkeys(row["brand"] for row in rows))
        for name in names:
            brand_rows = [row for row in rows if row["brand"] == name]
            pending = sum(1 for row in brand_rows if row["status"] == "PENDING")
            parts.append(f"{name}: {len(brand_rows)} rows, {pending} pending")
        self._brand_line.set("   ".join(parts))


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


def _ids(raw: object) -> set[str]:
    if not isinstance(raw, list):
        return set()
    return {str(item.get("id") or "") for item in raw if isinstance(item, dict) and item.get("id")}


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
