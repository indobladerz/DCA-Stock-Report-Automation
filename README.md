# DCA Stock Report Automation

Weekly stock (vehicle inventory) dashboard for **PT. Duta Cendana Adimandiri**
(Suzuki), sent Friday afternoon.

Every morning the upstream "ArUnit" system emails a *Notifikasi Stock* — a summary
line and a 176-row, 21-column table of every unit on the books. Read daily, it is a
wall of text. This repository turns the Friday edition of it into a weekly dashboard:
aging, capital tied up, per-branch and per-model roll-ups, and the data-quality defects
the raw table hides.

The daily ArUnit mail keeps running and is unaffected; this is the weekly read on top
of it, for the questions a daily unit list does not answer.

| | |
|---|---|
| Routine | [`routines/dca-stock-notification.md`](routines/dca-stock-notification.md) |
| Instructions the routine follows | [`routines/dca-stock-notification.prompt.txt`](routines/dca-stock-notification.prompt.txt) |
| Parser | [`src/parse_stock.py`](src/parse_stock.py) |
| Renderer | [`src/render_dashboard.py`](src/render_dashboard.py) |
| Tests | `python3 tests/test_parse_stock.py` |

No dependencies. Pure Python standard library, deliberately — see below.

---

## Why there is no PDF

**This is the fix for the dry run that hung.** Read this before changing anything
about delivery.

The obvious design — render the report to PDF and attach it — cannot work here, and
does not fail loudly when it doesn't. It hangs with the email unsent.

The mechanism is documented in
[`.claude/skills/base64-binary-payloads/SKILL.md`](.claude/skills/base64-binary-payloads/SKILL.md).
In short: the mail and Drive tools accept a file only as an inline base64 string —
there is no path parameter, no file id, no stream — so the model has to emit the whole
payload as one exact, high-entropy tool-call argument. Nothing rejects a long payload.
Reliability just decays with length until a single emission stops completing.

Measurements carried over from the sibling
[`financial-report-automation`](https://github.com/indobladerz/financial-report-automation)
repo, where this was worked out against real payloads:

| Payload | base64 chars | Result |
|---|---|---|
| Logo PNG | 4,280 | byte-identical |
| 9 KB PDF slice | 12,000 | byte-identical |
| 21 KB PDF | 20,972 | byte-identical |
| DCM monthly report | ~60,000 | never completed |
| DCA monthly report | 83,828 | never completed |

The practical ceiling for one emission sat around 22,000 characters.

**The stock report is much worse than the monthly financial report, not better.**
That report is a one-page summary; this one is a 176-row × 21-column ledger. Even
rendered with ReportLab — base-14 fonts, nothing embedded, the trick that rescued the
financial pipeline — the table alone lands in the tens of kilobytes, so its base64 is
several times past the ceiling. There is no shrink that closes that gap: the file size
tracks the number of rows, and the rows are the report.

So the answer is not a smaller PDF. It is no PDF.

**What the pipeline does instead.** The dashboard *is* the email — it travels as
`htmlBody`, an ordinary UTF-8 string parameter. No encoding step, no padding, no
exactness requirement, no size cliff: about 30 KB of low-entropy, human-readable
markup. That the upstream ArUnit email already delivers a ~480 KB HTML body every
morning is the existence proof.

Consequences of that choice, all deliberate:

- **No `attachments` array is ever passed to the Gmail tool.** Not "a small one" —
  none. The moment an attachment is reintroduced, the failure returns.
- **No `base64Content` is ever passed to the Drive tool**, and there is no Drive
  archive step. Nothing in this pipeline needs one.
- **The Artifact is the rich version**, published to a stable URL that updates in
  place each week. Its URL is never emailed to anyone — the recipients are dealership
  staff, not Claude users, and a link none of them can open is worse than no link.
  Both email bodies are complete on their own.
- **No `pip install`.** The old PDF path pulled in WeasyPrint (fragile) and then
  ReportLab. Removing the PDF removed the dependency, so a cold sandbox has nothing
  to install and nothing to fail at.

If a future change appears to need base64 here, the design has been broken. Stop and
say so rather than working around it.

---

## What the report adds to the source email

The source email already lists every unit, so restating the list is worthless. What it
does not do:

**Aging.** Days since DO, bucketed, for unsold units only. As of the 29 Aug 2026
sample: 62 units at 0–30 days, 16 at 31–60, 4 at 61–90, and **8 above 90 days** —
one of them 576 days old.

**Capital.** HPP rolled up per bucket, branch and model, so "8 old units" reads as
**Rp 1,48 M tied up**, against Rp 16,25 M of unsold stock in total.

**Reconciliation.** The source's four headline counters all reconcile against its own
table — but `Total Stock` counts FREE + MATCHING (90), *not* the table's 173 real
rows. The 78 SOLD units and 5 rows carrying no status at all sit in the same table and
are counted by no headline figure. The dashboard states this rather than letting the
reader assume the top-line number is the ledger. The pipeline aborts and mails a
`[PERIKSA]` warning to the owner alone if any counter ever stops reconciling.

**Data quality.** From the same sample: 5 duplicate DO numbers (each appearing twice —
once complete, once with no location or status), 9 rows with no location, 8 with no
status, 4 missing chassis and engine numbers, and 3 placeholder rows priced at Rp 0 or
Rp 123. Real upstream defects, invisible in a 176-row table.

---

## Design

Two renderers, one visual system, defined once at the top of
[`src/render_dashboard.py`](src/render_dashboard.py):

- petrol accent `#0f5563` on cool near-neutrals; status colours for FREE / MATCHING /
  SOLD kept separate from the fresh → critical severity ramp used for aging
- Archivo for display and UI, IBM Plex Mono for every figure, DO number and VIN — the
  vernacular of a stock sheet
- hairline rules rather than heavy cards; the dashboard stays deliberately minimal

The Artifact version adds webfonts, both colour themes, and a status filter over the
full ledger. The email versions drop webfonts and script (mail clients strip both),
inline every style, and stop at the summary — the full unit list stays in the upstream
ArUnit email, which is not going away.

**Two email variants.** `render_email(metrics, hpp=True)` produces email A, which
carries the cost figures and goes to the owner and the stock desk;
`hpp=False` produces email B for everyone else, with no rupiah figure anywhere. B is
not A with the numbers blanked — the HPP columns are removed and the stock-value
headline tile is replaced by the sold count, so B reads as a complete report rather
than a redacted one. A blanked cell still announces that a figure is being withheld;
a missed one leaks it. The tests assert B contains no `Rp` and no `HPP` at all, and
that both variants keep the same rows and the same four headline tiles. See
[`routines/dca-stock-notification.md`](routines/dca-stock-notification.md) for the
two recipient lists.

## Delivery integrity

Two controls, both added after real failures.

**Every email body is content-sealed.** The renderer appends a sentinel as the last
line — `<!-- dca-stok v1 a 2026-09-11 51c5126a98547957 -->` — carrying the variant, the
report date, and a SHA-256 prefix of everything above it. The run must confirm the body
it is about to send ends with exactly that line, and after sending it re-reads both
sent copies and checks `sizeEstimate > 15000` and that the snippet starts with
"PT. Duta Cendana Adimandiri".

This exists because on 4 September 2026 a run pasted
`<html><body> PLACEHOLDER </body></html>` into list A — the owner and finance among
them — and followed it with a correction. The stub was 1,363 bytes against a normal
25–31 KB, so the size check alone now catches it. `verify_sealed()` also rejects a
truncated body and a sentinel moved between variants; the tests assert all three.

**The Artifact publish runs last and may fail.** Two runs stalled for hours — 4 September
for about three, 11 September for nearly three days — with the emails stuck behind a
publish step that ran before them. The cause was never established; see
[`routines/dca-stock-notification.md`](routines/dca-stock-notification.md), which records
what is actually known rather than the tidier story. The fix does not depend on knowing:
the publish now runs after both emails are confirmed delivered, so whatever stalls there
can no longer hold the report. The artifact is the owner's reference copy and its link is
never sent to anyone, so losing it costs nothing.

## Layout

```
src/parse_stock.py       email plaintext -> normalised units + metrics JSON
src/render_dashboard.py  metrics -> out/artifact.html + out/email-{a,b}.html
routines/                the scheduled routine: metadata + full instructions
loaders/                 the ~1.5 KB prompt the trigger config actually stores
tests/                   fixture (a real captured email) + assertions
```

The routine clones `main`, which is where all of this lives, and loads its instructions
from that checkout. So `git push` is the whole deployment — no routine edit, no branch
checkout. The one thing `git push` cannot change is the routine's own permission
config; that is a web-UI step, documented in
[`routines/dca-stock-notification.md`](routines/dca-stock-notification.md).
