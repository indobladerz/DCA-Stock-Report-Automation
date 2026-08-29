"""Parse the daily ArUnit "Notifikasi Stock" email into normalised unit rows + metrics.

Input is the PLAIN_TEXT body Gmail returns for the notification, which renders the
HTML table as a markdown pipe table. Nothing here touches binary or base64: the whole
pipeline moves text only, by design (see README, "Why there is no PDF").
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import date, datetime

# The header the source table always emits, in order.
COLUMNS = [
    "no_do", "tanggal_do", "kode_mobil", "nama_mobil", "varian", "warna", "tahun",
    "chassis_code", "no_rangka", "engine_code", "no_mesin", "faktur",
    "bln_naik_faktur", "lokasi", "harga", "kpt_kf", "acs2", "subsidi", "hpp",
    "status", "cabang",
]

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

# Aging buckets, in days since DO. Ordered; last bucket is open-ended.
AGING_BUCKETS = [(0, 30, "0-30 hari"), (31, 60, "31-60 hari"),
                 (61, 90, "61-90 hari"), (91, None, "> 90 hari")]

# A unit priced below this is a placeholder row, not a real vehicle.
MIN_PLAUSIBLE_HPP = 10_000_000


def parse_rupiah(cell: str) -> int:
    """'Rp 252.580.000' -> 252580000. Blank or unparseable -> 0."""
    digits = re.sub(r"[^0-9]", "", cell or "")
    return int(digits) if digits else 0


def parse_do_date(cell: str):
    """'24-Oct-2025' -> date(2025, 10, 24). Unparseable -> None."""
    m = re.match(r"^\s*(\d{1,2})-([A-Za-z]{3})-(\d{4})\s*$", cell or "")
    if not m:
        return None
    day, mon, year = m.group(1), m.group(2).title(), m.group(3)
    if mon not in MONTHS:
        return None
    try:
        return date(int(year), MONTHS[mon], int(day))
    except ValueError:
        return None


def split_row(line: str) -> list[str]:
    """Split one markdown table row into its cells."""
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


@dataclass
class Unit:
    no_do: str = ""
    tanggal_do: str = ""
    kode_mobil: str = ""
    nama_mobil: str = ""
    varian: str = ""
    warna: str = ""
    tahun: str = ""
    chassis_code: str = ""
    no_rangka: str = ""
    engine_code: str = ""
    no_mesin: str = ""
    faktur: str = ""
    bln_naik_faktur: str = ""
    lokasi: str = ""
    harga: int = 0
    kpt_kf: int = 0
    acs2: int = 0
    subsidi: int = 0
    hpp: int = 0
    status: str = ""
    cabang: str = ""
    # derived
    do_date: str | None = None
    age_days: int | None = None
    aging_bucket: str = "tanggal DO tidak terbaca"
    flags: list[str] = field(default_factory=list)

    @property
    def is_placeholder(self) -> bool:
        return "baris placeholder" in self.flags


def parse_summary(body: str) -> dict[str, int]:
    """Read the four headline counters the source email prints above the table."""
    claimed: dict[str, int] = {}
    for value, label in re.findall(r"###\s*([\d.,]+)\s*(Total Stock|Stock Free|Stock Matching|Stock Sold)", body):
        claimed[label] = int(re.sub(r"[^0-9]", "", value))
    return claimed


def parse_units(body: str) -> list[Unit]:
    lines = body.splitlines()
    header_idx = next(
        (i for i, ln in enumerate(lines) if "NO DO" in ln and "TANGGAL DO" in ln and "|" in ln),
        None,
    )
    if header_idx is None:
        raise ValueError("tabel stock tidak ditemukan: baris header 'NO DO | TANGGAL DO' tidak ada")

    units: list[Unit] = []
    for line in lines[header_idx + 1:]:
        if "|" not in line:
            if units:
                break          # table ended
            continue
        cells = split_row(line)
        if set("".join(cells).strip()) <= set("-: "):
            continue           # markdown separator row
        if len(cells) < len(COLUMNS):
            cells += [""] * (len(COLUMNS) - len(cells))
        raw = dict(zip(COLUMNS, cells[:len(COLUMNS)]))
        if not raw["no_do"]:
            continue

        u = Unit(**{k: raw[k] for k in COLUMNS if k not in
                    ("harga", "kpt_kf", "acs2", "subsidi", "hpp")})
        u.harga = parse_rupiah(raw["harga"])
        u.kpt_kf = parse_rupiah(raw["kpt_kf"])
        u.acs2 = parse_rupiah(raw["acs2"])
        u.subsidi = parse_rupiah(raw["subsidi"])
        u.hpp = parse_rupiah(raw["hpp"])
        u.status = (raw["status"] or "").strip().upper()
        units.append(u)
    return units


def enrich(units: list[Unit], as_of: date) -> None:
    """Attach derived age, bucket and per-row data-quality flags, in place."""
    seen_do: Counter[str] = Counter(u.no_do for u in units)

    for u in units:
        d = parse_do_date(u.tanggal_do)
        if d:
            u.do_date = d.isoformat()
            u.age_days = (as_of - d).days
            for lo, hi, label in AGING_BUCKETS:
                if u.age_days >= lo and (hi is None or u.age_days <= hi):
                    u.aging_bucket = label
                    break

        if u.status in ("", "-"):
            u.flags.append("status kosong")
        if u.hpp < MIN_PLAUSIBLE_HPP:
            u.flags.append("baris placeholder")
        if not u.no_rangka:
            u.flags.append("no rangka kosong")
        if not u.no_mesin:
            u.flags.append("no mesin kosong")
        if not u.lokasi:
            u.flags.append("lokasi kosong")
        if seen_do[u.no_do] > 1:
            u.flags.append("no DO ganda")


def build_metrics(units: list[Unit], claimed: dict[str, int], as_of: date) -> dict:
    real = [u for u in units if not u.is_placeholder]

    by_status: Counter[str] = Counter()
    for u in real:
        by_status[u.status if u.status not in ("", "-") else "TANPA STATUS"] += 1

    unsold = [u for u in real if u.status in ("FREE", "MATCHING")]
    free = [u for u in real if u.status == "FREE"]
    matching = [u for u in real if u.status == "MATCHING"]
    sold = [u for u in real if u.status == "SOLD"]

    # Aging is only meaningful for stock still on the books.
    aging: dict[str, dict] = {}
    for _, _, label in AGING_BUCKETS:
        bucket = [u for u in unsold if u.aging_bucket == label]
        aging[label] = {"count": len(bucket), "value": sum(u.hpp for u in bucket)}
    undated = [u for u in unsold if u.age_days is None]
    if undated:
        aging["tanggal DO tidak terbaca"] = {
            "count": len(undated), "value": sum(u.hpp for u in undated)}

    def group(rows, key):
        out: dict[str, dict] = defaultdict(lambda: {"count": 0, "value": 0, "free": 0,
                                                    "matching": 0, "sold": 0})
        for u in rows:
            k = (getattr(u, key) or "TANPA LOKASI").strip().upper()
            out[k]["count"] += 1
            out[k]["value"] += u.hpp
            if u.status == "FREE":
                out[k]["free"] += 1
            elif u.status == "MATCHING":
                out[k]["matching"] += 1
            elif u.status == "SOLD":
                out[k]["sold"] += 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]["count"]))

    ageing_over_90 = sorted(
        [u for u in unsold if (u.age_days or 0) > 90], key=lambda u: -(u.age_days or 0))

    # Reconciliation: what the source email claims vs what its own table contains.
    # "Total Stock" in the source counts FREE + MATCHING only -- stock still on hand.
    # It is not the row count: SOLD units and rows with no status sit in the same
    # table and are counted by no headline figure at all.
    computed = {
        "Total Stock": len(unsold),
        "Stock Free": len(free),
        "Stock Matching": len(matching),
        "Stock Sold": len(sold),
    }
    reconciliation = [
        {"label": k, "claimed": claimed.get(k), "computed": v,
         "match": claimed.get(k) == v}
        for k, v in computed.items()
    ]
    # Units present in the table that no headline counter accounts for.
    uncounted = len(real) - len(unsold) - len(sold)

    issue_counts: Counter[str] = Counter()
    for u in units:
        for f in u.flags:
            issue_counts[f] += 1
    dup_dos = sorted({u.no_do for u in units if "no DO ganda" in u.flags})

    return {
        "as_of": as_of.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rows_in_table": len(units),
        "placeholder_rows": len(units) - len(real),
        "counts": {
            "total": len(real), "free": len(free), "matching": len(matching),
            "sold": len(sold), "unsold": len(unsold),
            "no_status": by_status.get("TANPA STATUS", 0),
        },
        "value": {
            "unsold_hpp": sum(u.hpp for u in unsold),
            "free_hpp": sum(u.hpp for u in free),
            "matching_hpp": sum(u.hpp for u in matching),
            "total_hpp": sum(u.hpp for u in real),
            "over_90_hpp": sum(u.hpp for u in ageing_over_90),
        },
        "aging": aging,
        "by_model": group(real, "nama_mobil"),
        "by_location": group(unsold, "lokasi"),
        "by_status": dict(by_status),
        "over_90": [asdict(u) for u in ageing_over_90],
        "oldest_unsold": [asdict(u) for u in
                          sorted([u for u in unsold if u.age_days is not None],
                                 key=lambda u: -(u.age_days or 0))[:15]],
        "reconciliation": reconciliation,
        "uncounted_rows": uncounted,
        "claimed": claimed,
        "data_quality": {"issues": dict(issue_counts), "duplicate_do": dup_dos},
        "units": [asdict(u) for u in units],
    }


def run(body: str, as_of: date | None = None) -> dict:
    units = parse_units(body)
    if not units:
        raise ValueError("tabel stock kosong: 0 baris unit terbaca")
    if as_of is None:
        as_of = date.today()
    enrich(units, as_of)
    return build_metrics(units, parse_summary(body), as_of)


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    as_of = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
    print(json.dumps(run(text, as_of), ensure_ascii=False, indent=2))
