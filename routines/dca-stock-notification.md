# DCA Weekly Stock Dashboard

| | |
|---|---|
| **Entity** | PT. Duta Cendana Adimandiri (Suzuki) |
| **Trigger ID** | `trig_01UpN42Pf7LkRANbQyETQZxq` ("DCA Weekly Stock Dashboard V2") |
| **Schedule** | `0 9 * * 5` (UTC) — **Friday 16:00 WIB** |
| **Source** | Gmail: subject `Notifikasi Stock`, from `stockdcasystem@gmail.com` (previously `ar.dutacendana@gmail.com`), sent ~09:00 WIB daily |
| **Prompt** | [`dca-stock-notification.prompt.txt`](dca-stock-notification.prompt.txt) |
| **Loader** | [`../loaders/dca-stock-loader.txt`](../loaders/dca-stock-loader.txt) |
| **Branch** | everything runs from `main`; the routine clones the default branch |
| **Artifact URL** | <https://claude.ai/code/artifact/e17b5d29-f665-44fa-95f6-10d7a6b7d586> |

The upstream ArUnit notification arrives every morning; this report is the Friday-afternoon
read of it. If Friday's notification is missing the run falls back to the newest one
within 4 days and labels the report with that email's own date; older than that, the run
is a silent no-op rather than reporting stale numbers.

## Distribution lists — two emails, two audiences

Each week goes out as **two sends sharing one subject**, differing only in whether
cost figures are present.

| | Email A — with HPP | Email B — no HPP |
|---|---|---|
| **To** | `vwilliam@dutacendana.com`<br>`stock@suzukidutacendana.com`<br>`fineke99@gmail.com`<br>`om@suzukidutacendana.com`<br>`finance@suzukidutacendana.com` | `it@dutacendana.com`<br>`all.bm@suzukidutacendana.com`<br>`m.rizky@smkwikrama.sch.id` |
| **Body** | `out/email-a.html` | `out/email-b.html` |
| **Cost figures** | stock value, HPP per bucket / branch / model, HPP per aging unit | none anywhere |

These cover the six recipients of the upstream ArUnit notification, plus
`all.bm@suzukidutacendana.com` on list B. No one appears on both, and the two lists
are never CC'd across.

`all.bm@` is a **group alias** — it expands to the branch managers, and its membership
lives in Google Workspace rather than here. That is fine on list B, which carries no
cost data. It would not be fine on list A: never put a group alias on the with-HPP
list without knowing every address inside it, because a single B-audience member
hidden in an A alias leaks the cost figures. If someone on list A is also inside
`all.bm@`, they simply receive both emails, which is harmless — A is the fuller report.

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

The pipeline lives on `main`, which is the branch the routine clones, so a change is
deployed by `git push` alone. No routine edit, no branch checkout.

The superseded routine `trig_01QUuaBJQPr3XSXUDEbDfqx3` is **disabled** — do not
re-enable it. `trig_01UpN42Pf7LkRANbQyETQZxq` is the live one.

### The runs that hung, and what we actually know

Two runs took far longer than the ~12 minutes this pipeline needs:

| Run | Fired | Finished | Elapsed |
|---|---|---|---|
| Fri 4 Sep 2026 | 10:08 | 13:10 | ~3 hours |
| Fri 11 Sep 2026 | 09:11 | **Sun 14 Sep 02:54** | **~2 days 17 hours** |

Both eventually delivered. **The cause is not established.** What is known:

- A manually forced run on 29 Aug 2026 *did* block on a permission prompt —
  `pending_action: mcp__Gmail__search_threads` was observed live. That run's origin was
  `force_run_trigger`, not a scheduled fire.
- For the 4 and 11 Sep runs, both had already finished when they were examined, so no
  pending action was ever seen. That they were blocked on a permission prompt is an
  **inference from timing**, not an observation.
- The routines documentation states that routines "run autonomously as full Claude Code
  cloud sessions: there is no permission-mode picker and no approval prompts during a
  run", which sits badly with the observed durations either way.

`.claude/settings.json` in this repository is not the lever some earlier notes assumed.
It was on `main` from 2 September, before both long runs, with `Artifact` and the Gmail
tools already in its allow list. Whatever stalled those runs, that file did not prevent
it.

**To establish the cause**, open the run itself — a green run status only means the
session exited without an infrastructure error, and permission denials and tool errors
surface in the transcript rather than the status. The 11 Sep run is
`session_01QjaYvA48jdfRp9BWtNwcf6`. From a local terminal (not a web session),
`/schedule why did ... take three days?` reads the run log and explains, on CLI
v2.1.227 or later.

**What was done anyway**, because it holds regardless of cause: the Artifact publish
moved to the end of the run (STEP 7) and is explicitly allowed to fail. Whatever stalls
there can no longer hold the emails, because by then the report is already delivered.

## Incident log

**4 Sep 2026 — placeholder body sent to list A.** At 13:06 the five list-A recipients,
owner and finance included, received a body reading
`<html><body> PLACEHOLDER </body></html>`, followed at 13:08 by a correction subject-lined
"(koreksi isi email sebelumnya)". The run pasted a stub instead of the rendered file
and nothing checked it.

Fixed in three layers, because a prompt that merely asks for care is not a control:

- The renderer now **seals each body** with a sentinel — `<!-- dca-stok v1 a
  2026-09-11 51c5126a… -->` — carrying the variant, report date and a hash of
  everything above it. It is the last line of the file.
- STEP 6 will not send unless the last line of the assembled body is exactly that
  sentinel, and forbids stubs, shortened bodies and "send then correct" outright.
- STEP 6.5 re-reads both sent copies and checks `sizeEstimate > 15000` and that the
  snippet starts with "PT. Duta Cendana Adimandiri". The placeholder was 1,363 bytes,
  so that check alone would have caught it.

## What can and cannot be configured in the web UI

At <https://claude.ai/code/routines>, open **DCA Weekly Stock Dashboard V2**
(`trig_01UpN42Pf7LkRANbQyETQZxq`) and click the **pencil icon** for **Edit routine**.

The form has five sections and no others: **name + prompt** (with a model selector),
**repositories**, **environment**, **select a trigger**, and **connectors**. There is
**no tools or permissions control** — do not go looking for one. Per-tool approval is
not something a routine exposes.

So the only tool-scoping lever is **Connectors**, and the one change worth making is:

- **Remove Google Drive.** This pipeline is text-only and its settings file denies every
  Drive tool; an included connector grants unprompted access to all of its tools, writes
  included, so there is no reason to carry it.
- **Keep Gmail.** The run reads the source notification and sends the two reports.

`Artifact` is not a connector, so nothing in this form governs it. That is why STEP 7 of
the prompt now runs the publish last and lets it fail rather than relying on a grant
that has no UI.

While you are in the edit form, the **Instructions** box should match
[`../loaders/dca-stock-loader.txt`](../loaders/dca-stock-loader.txt). A Claude Code
session cannot update it — this routine was created via the HTTP API, and the trigger
API refuses prompt edits from agents on routines they did not create.

After saving, use **Run now** and watch it. A green status only means the session
exited cleanly; open the run and confirm both emails went out. A run much longer than
about fifteen minutes is the symptom to watch for.

## Running it by hand

```
python3 tests/test_parse_stock.py                              # must PASS first
python3 src/parse_stock.py out/source.md 2026-08-29 > out/metrics.json
python3 src/render_dashboard.py out/metrics.json   # -> artifact.html, email-a, email-b
```

`out/source.md` is the `plaintextBody` of the source email, saved verbatim.
A captured example is in [`../tests/fixtures/`](../tests/fixtures/).
