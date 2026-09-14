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

### The permission problem, and what actually fixes it

Two runs hung waiting for a permission prompt nobody was there to answer:

| Run | Fired | Finished | Blocked for |
|---|---|---|---|
| Fri 4 Sep 2026 | 10:08 | 13:10 | ~3 hours |
| Fri 11 Sep 2026 | 09:11 | **Sun 14 Sep 02:54** | **~2 days 17 hours** |

Both eventually delivered, but only once a human cleared the prompt.

`.claude/settings.json` in this repository does **not** fix it, despite what an
earlier attempt assumed. That file was on `main` from 2 September, before both hung
runs. A repository settings file is not what gates an unattended run; the routine's
own stored config is:

```
allowed_tools : Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch
connectors    : Gmail, Google-Drive
```

`Artifact` is in neither list — it is not a connector tool, so attaching Gmail does
nothing for it. On 11 September the artifact was republished at 02:49:57 and the two
emails went out at 02:52 and 02:54, which puts the block at the Artifact call.

Two mitigations, both applied:

1. **The Artifact publish moved to the end of the run** (STEP 7) and is explicitly
   allowed to fail. The emails are the deliverable; a prompt at the artifact step now
   costs nothing, because the report is already out.
2. **The permission itself still needs granting in the web UI** — see the
   *Granting permissions* section below. Do both: the reorder limits the damage, the
   grant removes the prompt.

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

## Granting permissions in the web UI

Do this once, at <https://claude.ai/code/routines>. It cannot be done from a Claude
Code session — the trigger API available there rejects the connector/permission
fields, which is how the routine ended up prompting in the first place.

1. Open **DCA Weekly Stock Dashboard V2** (`trig_01UpN42Pf7LkRANbQyETQZxq`).
   Ignore the older, disabled **DCA Weekly Stock Dashboard**.
2. Click the **pencil icon** to open **Edit routine**.
3. Scroll to **Connectors** at the bottom of the form. Confirm **Gmail** is present.
   Remove **Google Drive** — this pipeline is text-only and denies every Drive tool
   anyway, and an included connector grants unprompted access to all of its tools,
   writes included.
4. If the connector row exposes a tool list, restrict Gmail to the four tools the run
   actually uses: `search_threads`, `get_thread`, `get_message`, `send_message`.
   Leave the trash/delete tools out.
5. Look for a tools or permissions control in the same form and make sure **Artifact**
   is allowed. This is the one that has been blocking — it is not a connector tool, so
   step 3 does not cover it. If the form offers no way to allow it, leave it: STEP 7 of
   the prompt now runs the artifact publish last and lets it fail, so the emails still
   go out on time.
6. **Save.**
7. Test with **Run now** on the detail page, and watch it. A green run status only
   means the session exited without an infrastructure error — open the run and confirm
   both emails actually went out, and check the run's duration. Anything over about
   fifteen minutes means it is sitting on a prompt again.

## Running it by hand

```
python3 tests/test_parse_stock.py                              # must PASS first
python3 src/parse_stock.py out/source.md 2026-08-29 > out/metrics.json
python3 src/render_dashboard.py out/metrics.json   # -> artifact.html, email-a, email-b
```

`out/source.md` is the `plaintextBody` of the source email, saved verbatim.
A captured example is in [`../tests/fixtures/`](../tests/fixtures/).
