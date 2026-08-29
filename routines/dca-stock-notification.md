# DCA Daily Stock Notification Dashboard

| | |
|---|---|
| **Entity** | PT. Duta Cendana Adimandiri (Suzuki) |
| **Trigger ID** | _not yet deployed — see "Deploying" below_ |
| **Schedule** | `0 3 * * *` (UTC) — 10:00 WIB, daily |
| **Source** | Gmail: subject `Notifikasi Stock`, from `stockdcasystem@gmail.com` (previously `ar.dutacendana@gmail.com`), sent ~09:00 WIB daily |
| **Prompt** | [`dca-stock-notification.prompt.txt`](dca-stock-notification.prompt.txt) |
| **Loader** | [`../loaders/dca-stock-loader.txt`](../loaders/dca-stock-loader.txt) |
| **Artifact URL** | <https://claude.ai/code/artifact/e17b5d29-f665-44fa-95f6-10d7a6b7d586> |

The routine runs an hour after the upstream email lands, so a late upstream send does
not race it. If the source email is missing, the run is a silent no-op by design.

## Distribution list

The report currently goes to **`vwilliam@dutacendana.com` only**. This is the
deliberate starting point: the automation sends outward-facing daily mail, so it
begins with the owner alone and is widened once the output has been reviewed in
production for a few days.

The upstream ArUnit notification already goes to the full team:

```
it@dutacendana.com
om@suzukidutacendana.com
vwilliam@dutacendana.com
fineke99@gmail.com
stock@suzukidutacendana.com
m.rizky@smkwikrama.sch.id
```

To widen the distribution, edit STEP 7 of the prompt file to name the recipients
above and `git push`. No routine edit is required.

## Deploying

The routine is not yet created. To create it, point a daily trigger at this
repository with `loaders/dca-stock-loader.txt` as its inline prompt:

- `environment_id`: the same cloud environment the financial-report routines use
- `sources`: `https://github.com/indobladerz/DCA-Stock-Report-Automation`
- `create_new_session_on_fire`: true
- `cron_expression`: `0 3 * * *`

Record the returned `trig_...` id in the table above.

Because the loader is only ~1.5 KB and the real instructions live in this repo, a
change to the report afterwards is deployed by `git push` alone — the routine config
never needs to be touched again.

## Running it by hand

```
python3 tests/test_parse_stock.py                              # must PASS first
python3 src/parse_stock.py out/source.md 2026-08-29 > out/metrics.json
python3 src/render_dashboard.py out/metrics.json [artifact-url]
```

`out/source.md` is the `plaintextBody` of the source email, saved verbatim.
A captured example is in [`../tests/fixtures/`](../tests/fixtures/).
