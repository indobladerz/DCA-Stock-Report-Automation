# DCA Weekly Stock Dashboard

| | |
|---|---|
| **Entity** | PT. Duta Cendana Adimandiri (Suzuki) |
| **Trigger ID** | `trig_01QUuaBJQPr3XSXUDEbDfqx3` |
| **Schedule** | `0 10 * * 5` (UTC) — **Friday 17:00 WIB** |
| **Source** | Gmail: subject `Notifikasi Stock`, from `stockdcasystem@gmail.com` (previously `ar.dutacendana@gmail.com`), sent ~09:00 WIB daily |
| **Prompt** | [`dca-stock-notification.prompt.txt`](dca-stock-notification.prompt.txt) |
| **Loader** | [`../loaders/dca-stock-loader.txt`](../loaders/dca-stock-loader.txt) |
| **Artifact URL** | <https://claude.ai/code/artifact/e17b5d29-f665-44fa-95f6-10d7a6b7d586> |

The upstream ArUnit notification arrives every morning; this report is the Friday-evening
read of it. If Friday's notification is missing the run falls back to the newest one
within 4 days and labels the report with that email's own date; older than that, the run
is a silent no-op rather than reporting stale numbers.

## Distribution lists — two emails, two audiences

Each week goes out as **two sends sharing one subject**, differing only in whether
cost figures are present.

| | Email A — with HPP | Email B — no HPP |
|---|---|---|
| **To** | `vwilliam@dutacendana.com`<br>`stock@suzukidutacendana.com` | `it@dutacendana.com`<br>`om@suzukidutacendana.com`<br>`fineke99@gmail.com`<br>`m.rizky@smkwikrama.sch.id` |
| **Body** | `out/email-a.html` | `out/email-b.html` |
| **Cost figures** | stock value, HPP per bucket / branch / model, HPP per aging unit | none anywhere |

Between them these are the six recipients of the upstream ArUnit notification.
No one appears on both, and the two lists are never CC'd across.

**B is not A with the numbers blanked out.** The renderer removes the HPP columns
entirely and replaces the stock-value headline tile with the sold count, so B reads as
a complete report rather than one with holes in it. That is why B must always come
from `render_email(metrics, hpp=False)` and never from hand-editing A — a blanked cell
still tells the reader a figure exists and is being withheld, and a missed one leaks
it outright. The test suite asserts B contains no `Rp` and no `HPP` at all.

The two sends share a subject, so the duplicate-send guard is **per recipient**, not
per subject — otherwise a run that sent A and failed on B would mark the week done and
silently never deliver B.

Neither email carries the Artifact URL. The recipients are dealership staff, not
Claude users; a link none of them can open is worse than no link, and both bodies are
complete on their own. The Artifact is the account owner's reference copy.

To change either list, edit STEP 7 of the prompt file and `git push`. No routine edit
is required.

Note that the upstream ArUnit mail already goes to all six *daily*; this weekly report
is a different thing — the Friday read of aging and capital — not a replacement for it.

## Deploying

The routine exists (`trig_01QUuaBJQPr3XSXUDEbDfqx3`, first fire Fri 4 Sep 2026
10:04 UTC). Two things still need attaching **by hand in the web UI**, because the
trigger API available to an assistant session cannot set either:

1. **Gmail connector.** The trigger was created with no MCP connectors, so the
   sessions it fires have no `mcp__Gmail__*` tools — it cannot read the source
   notification or send the report. Without this it no-ops every week (safely, but
   uselessly). Attach Gmail at <https://claude.ai/code/routines>.
2. **Repository source.** The trigger has no `sources` entry, so the checkout its
   instructions live in is not cloned. Add
   `https://github.com/indobladerz/DCA-Stock-Report-Automation` as a source in the
   same screen.

Until both are attached, STEP B of the loader applies and the run ends quietly rather
than improvising — which is the intended failure mode, not a working schedule.

For reference, the two financial-report routines in the sibling repo carry exactly
this configuration (Gmail + Drive connectors, repo as a source); copying their setup
is the quickest path.

Because the loader is only ~1.5 KB and the real instructions live in this repo, a
change to the report afterwards is deployed by `git push` alone — the routine config
never needs to be touched again.

## Running it by hand

```
python3 tests/test_parse_stock.py                              # must PASS first
python3 src/parse_stock.py out/source.md 2026-08-29 > out/metrics.json
python3 src/render_dashboard.py out/metrics.json   # -> artifact.html, email-a, email-b
```

`out/source.md` is the `plaintextBody` of the source email, saved verbatim.
A captured example is in [`../tests/fixtures/`](../tests/fixtures/).
