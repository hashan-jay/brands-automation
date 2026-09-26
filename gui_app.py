"""Brand transaction window, laid out like the finance list."""
from __future__ import annotations

import threading
import tkinter as tk
from datetime import date
from tkinter import ttk

from src.transactions import BRANDS, display_rows, fetch_brand, load_tokens

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
}


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Brand transactions")
        self.geometry("1280x760")
        self.minsize(980, 560)
        self.configure(bg="#eef2f7")
        self._rows: list[dict[str, str]] = []
        self._brand_vars = {item["name"]: tk.BooleanVar(value=True) for item in BRANDS}
        self._date = tk.StringVar(value=date.today().isoformat())
        self._status = tk.StringVar(value="Choose a date, then load the brands.")
        self._tally = tk.StringVar(value="No rows yet.")
        self._style()
        self._build()

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
        tk.Label(header, text="Completed rows from each brand API", bg="#0f2744", fg="#c5d4e8", font=("Segoe UI", 9)).pack(anchor="w", padx=16)

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
        ttk.Button(side, text="Load transactions", style="Run.TButton", command=self._start).pack(anchor="w", pady=(14, 6))
        ttk.Label(side, textvariable=self._status, style="Muted.TLabel", wraplength=180).pack(anchor="w")

        main = ttk.Frame(body, style="Card.TFrame", padding=12)
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)
        bar = ttk.Frame(main, style="Card.TFrame")
        bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, text="Completed transactions", style="CardTitle.TLabel").pack(side="left")
        self._type = tk.StringVar(value="All types")
        combo = ttk.Combobox(bar, textvariable=self._type, state="readonly", width=14, values=("All types", "DEPOSIT", "WITHDRAW", "BONUS"))
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", lambda _event: self._fill())
        ttk.Label(bar, text="Type", style="Muted.TLabel").pack(side="right", padx=(0, 6))

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

    def _start(self) -> None:
        selected = [item for item in BRANDS if self._brand_vars[item["name"]].get()]
        if not selected:
            self._status.set("Select at least one brand.")
            return
        day = self._date.get().strip()
        self._status.set("Loading " + ", ".join(item["name"] for item in selected) + "…")
        threading.Thread(target=self._load, args=(selected, day), daemon=True).start()

    def _load(self, selected: list[dict], day: str) -> None:
        try:
            tokens = load_tokens()
        except Exception as exc:
            self.after(0, lambda: self._status.set(str(exc)))
            return
        collected: list[dict[str, str]] = []
        errors: list[str] = []
        for brand in selected:
            token = tokens.get(brand["name"], "")
            if not token:
                errors.append(brand["name"] + " has no token")
                continue
            try:
                raw, error = fetch_brand(brand, token, day)
            except Exception as exc:
                errors.append(f"{brand['name']}: {exc.__class__.__name__}")
                continue
            if error:
                errors.append(f"{brand['name']}: {error}")
            collected.extend(display_rows(raw, brand["name"]))
        self.after(0, lambda: self._show(collected, errors))

    def _show(self, rows: list[dict[str, str]], errors: list[str]) -> None:
        self._rows = rows
        if errors and not rows:
            self._status.set(" ".join(errors))
        elif errors:
            self._status.set(f"Loaded {len(rows)} rows. " + " ".join(errors))
        else:
            self._status.set(f"Loaded {len(rows)} completed rows.")
        self._fill()

    def _fill(self) -> None:
        self.tree.delete(*self.tree.get_children())
        wanted = self._type.get()
        visible = [row for row in self._rows if wanted == "All types" or row["type"] == wanted]
        total = 0.0
        for row in visible:
            self.tree.insert("", "end", values=tuple(row[key] for key in COLUMNS), tags=(row["type"],))
            try:
                total += float(row["amount"] or 0)
            except ValueError:
                pass
        deposits = sum(1 for row in visible if row["type"] == "DEPOSIT")
        withdraws = sum(1 for row in visible if row["type"] == "WITHDRAW")
        self._tally.set(
            f"Rows {len(visible)}   ·   Deposit {deposits}   ·   Withdraw {withdraws}   ·   Amount {total:,.2f}"
        )


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
