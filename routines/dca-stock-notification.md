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
| **To** | `vwilliam@dutacendana.com`<br>`stock@suzukidutacendana.com`<br>`fineke99@gmail.com`<br>`om@suzukidutacendana.com` | `it@dutacendana.com`<br>`all.bm@suzukidutacendana.com`<br>`m.rizky@smkwikrama.sch.id` |
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

The routine is live: `trig_01QUuaBJQPr3XSXUDEbDfqx3`, first fire **Fri 4 Sep 2026
10:05 UTC**. Verified attached:

- **Gmail connector** — and only Gmail. The other four connectors on the account
  (Drive, Calendar, Canva, Claude Code Remote) are deliberately absent: an included
  connector grants unprompted access to all of its tools, writes included, and this
  routine reads one mailbox and sends two emails.
- **Repository** `indobladerz/DCA-Stock-Report-Automation` as a source.

### One caveat: the default branch

A routine clones the repository's **default branch**. While this work sits on
`claude/dca-stock-notification-dashboard-2kqr8m` and not on `main`, the loader has to
check the branch out itself — STEP A.2 of [`../loaders/dca-stock-loader.txt`](../loaders/dca-stock-loader.txt)
does exactly that, and the live routine prompt carries the same text.

That is a working arrangement, not a good end state. **Merging the branch to `main`
removes the step entirely** and makes the checkout the routine already has correct on
its own. Until then, renaming or deleting the branch breaks the routine silently.

### Testing without waiting for Friday

Open the routine at <https://claude.ai/code/routines> and click **Run now** on its
detail page. Each run appears as a normal session, so the transcript shows exactly
what it did. Note that a green run status only means the session exited without an
infrastructure error — open the run to confirm both emails actually went out.

## Running it by hand

```
python3 tests/test_parse_stock.py                              # must PASS first
python3 src/parse_stock.py out/source.md 2026-08-29 > out/metrics.json
python3 src/render_dashboard.py out/metrics.json   # -> artifact.html, email-a, email-b
```

`out/source.md` is the `plaintextBody` of the source email, saved verbatim.
A captured example is in [`../tests/fixtures/`](../tests/fixtures/).
