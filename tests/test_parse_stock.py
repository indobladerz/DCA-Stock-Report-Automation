"""Run: python3 tests/test_parse_stock.py"""
import sys, pathlib
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import parse_stock as P                                          # noqa: E402
from render_dashboard import render_artifact, render_email, rp, rp_short  # noqa: E402

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "notifikasi-stock-2026-08-29.md"
AS_OF = date(2026, 8, 29)

failures = []


def check(name, got, want):
    if got != want:
        failures.append(f"{name}: got {got!r}, want {want!r}")


def check_true(name, cond, detail=""):
    if not cond:
        failures.append(f"{name}: false {detail}")


# --- unit-level helpers ---------------------------------------------------
check("rupiah plain", P.parse_rupiah("Rp 252.580.000"), 252580000)
check("rupiah blank", P.parse_rupiah(""), 0)
check("rupiah tiny", P.parse_rupiah("Rp 123"), 123)
check("date ok", P.parse_do_date("24-Oct-2025"), date(2025, 10, 24))
check("date blank", P.parse_do_date(""), None)
check("date junk", P.parse_do_date("kemarin"), None)
check("format rupiah", rp(16247776540), "Rp 16.247.776.540")
check("format short M", rp_short(16247776540), "Rp 16,25 M")
check("format short jt", rp_short(683755000), "Rp 683,8 jt")

# --- full pipeline against the real captured email ------------------------
m = P.run(FIXTURE.read_text(encoding="utf-8"), AS_OF)

check("rows parsed", m["rows_in_table"], 176)
check("placeholder rows dropped", m["placeholder_rows"], 3)
check("free", m["counts"]["free"], 79)
check("matching", m["counts"]["matching"], 11)
check("sold", m["counts"]["sold"], 78)
check("unsold", m["counts"]["unsold"], 90)
check("rows with no status", m["uncounted_rows"], 5)

# Every headline counter in the source email must reconcile against its own table.
for r in m["reconciliation"]:
    check_true(f"reconcile {r['label']}", r["match"],
               f"claimed={r['claimed']} computed={r['computed']}")

# Aging covers exactly the unsold population, no unit double-counted or dropped.
check("aging total == unsold", sum(b["count"] for b in m["aging"].values()),
      m["counts"]["unsold"])
check("units over 90d", len(m["over_90"]), 8)
check_true("over-90 sorted oldest first",
           all(a["age_days"] >= b["age_days"]
               for a, b in zip(m["over_90"], m["over_90"][1:])))

# Known duplicate DO numbers in the source feed.
check("duplicate DO numbers", m["data_quality"]["duplicate_do"],
      ["DB626180", "DB631791", "DB633014", "DB633830", "DB634542"])

# Value roll-ups must be internally consistent.
check("free + matching == unsold value",
      m["value"]["free_hpp"] + m["value"]["matching_hpp"], m["value"]["unsold_hpp"])
check("over-90 value == sum of over-90 rows",
      m["value"]["over_90_hpp"], sum(u["hpp"] for u in m["over_90"]))
check("by_location covers unsold",
      sum(r["count"] for r in m["by_location"].values()), m["counts"]["unsold"])
check("by_model covers real rows",
      sum(r["count"] for r in m["by_model"].values()),
      m["rows_in_table"] - m["placeholder_rows"])

# The "SBAM DB619731" prefix must survive as its own DO, not be split.
check_true("SBAM row kept intact",
           any(u["no_do"] == "SBAM DB619731" for u in m["units"]))

# --- renderers ------------------------------------------------------------
art, mail = render_artifact(m), render_email(m, "https://example.invalid/x")

check_true("artifact has title", art.lstrip().startswith("<title>"))
check_true("artifact defines light tokens first", art.index(":root {") < art.index("@media"))
check_true("artifact paints body", "background:var(--ground)" in art)
check_true("artifact ledger complete",
           art.count('<tr data-status=') == m["rows_in_table"])
check_true("email carries no attachment markup", "base64" not in mail.lower())
check_true("email has no script", "<script" not in mail.lower())
check_true("email has no webfont", "fonts.googleapis" not in mail)
check_true("email links the dashboard", "https://example.invalid/x" in mail)
# Reliability budget: an email body is plain text, but keep it sane.
check_true("email under 200 KB", len(mail.encode()) < 200_000, f"{len(mail.encode())} B")

# --- degenerate inputs ----------------------------------------------------
try:
    P.run("no table here at all", AS_OF)
    failures.append("missing table: expected ValueError")
except ValueError:
    pass

try:
    P.run("| NO DO | TANGGAL DO |\n|---|---|\n", AS_OF)
    failures.append("empty table: expected ValueError")
except ValueError:
    pass

if failures:
    print(f"FAIL ({len(failures)})")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("PASS - all checks green")
