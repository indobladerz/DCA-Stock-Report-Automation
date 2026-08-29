"""Render the stock metrics into (a) an Artifact dashboard and (b) an email body.

Design tokens, kept in one place so the two renderers stay one visual system:

  ground  #f6f7f8   surface #ffffff   ink   #14171b   muted #6a7381  line #e2e6ea
  accent  #0f5563 (petrol)
  status  free #0f5563 · matching #9a6a10 · sold #7b8494
  severity fresh #2c7551 · warn #9a6a10 · critical #a33529

Type: Archivo for display/UI, IBM Plex Mono for every figure and code -- the
vernacular of a stock sheet. The email drops the webfonts (mail clients strip
them) and keeps the same palette and hierarchy in inline styles.

Neither renderer produces or touches a binary. See README, "Why there is no PDF".
"""

from __future__ import annotations

import html
import json
import sys

C = {
    "ground": "#f6f7f8", "surface": "#ffffff", "ink": "#14171b", "muted": "#6a7381",
    "line": "#e2e6ea", "accent": "#0f5563",
    "free": "#0f5563", "matching": "#9a6a10", "sold": "#7b8494",
    "fresh": "#2c7551", "warn": "#9a6a10", "crit": "#a33529",
}

BUCKET_COLOR = {"0-30 hari": C["fresh"], "31-60 hari": "#5b7c8a",
                "61-90 hari": C["warn"], "> 90 hari": C["crit"]}

MONTHS_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
             "Agustus", "September", "Oktober", "November", "Desember"]


def e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def rp(n: int) -> str:
    """Full rupiah, Indonesian thousands separator."""
    return "Rp " + f"{int(n):,}".replace(",", ".")


def rp_short(n: int) -> str:
    """Rp 16,25 M / Rp 683,8 jt -- for headline tiles."""
    n = int(n)
    if abs(n) >= 1_000_000_000:
        return f"Rp {n / 1_000_000_000:,.2f} M".replace(".", "#").replace(",", ".").replace("#", ",")
    if abs(n) >= 1_000_000:
        return f"Rp {n / 1_000_000:,.1f} jt".replace(".", "#").replace(",", ".").replace("#", ",")
    return rp(n)


def id_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS_ID[int(m) - 1]} {y}"


# --------------------------------------------------------------------------
# Artifact dashboard
# --------------------------------------------------------------------------

def render_artifact(m: dict) -> str:
    c, v, aging = m["counts"], m["value"], m["aging"]
    unsold = max(c["unsold"], 1)

    seg = "".join(
        f'<div class="seg" style="flex:{d["count"]};background:{BUCKET_COLOR.get(k, C["muted"])}" '
        f'title="{e(k)}: {d["count"]} unit"></div>'
        for k, d in aging.items() if d["count"]
    )

    aging_rows = "".join(
        f"""<tr>
          <td><span class="dot" style="background:{BUCKET_COLOR.get(k, C['muted'])}"></span>{e(k)}</td>
          <td class="num">{d['count']}</td>
          <td class="num pct">{d['count'] / unsold * 100:.0f}%</td>
          <td class="num">{rp(d['value'])}</td>
        </tr>"""
        for k, d in aging.items() if d["count"]
    )

    def bar_row(name, row, denom, color):
        w = row["count"] / max(denom, 1) * 100
        return f"""<tr>
          <th scope="row">{e(name)}</th>
          <td class="barcell"><span class="bar" style="width:{w:.1f}%;background:{color}"></span></td>
          <td class="num">{row['count']}</td>
          <td class="num sub">{row['free']}</td>
          <td class="num sub">{row['matching']}</td>
          <td class="num">{rp_short(row['value'])}</td>
        </tr>"""

    max_model = max((r["count"] for r in m["by_model"].values()), default=1)
    model_rows = "".join(bar_row(k, r, max_model, C["accent"])
                         for k, r in m["by_model"].items())
    max_loc = max((r["count"] for r in m["by_location"].values()), default=1)
    loc_rows = "".join(bar_row(k, r, max_loc, C["free"])
                       for k, r in m["by_location"].items())

    over90 = "".join(
        f"""<tr>
          <td class="mono">{e(u['no_do'])}</td>
          <td>{e(u['nama_mobil'])} <span class="sub">{e(u['varian'])}</span></td>
          <td>{e(u['warna'])}</td>
          <td>{e(u['lokasi'] or '—')}</td>
          <td class="num"><strong class="crit">{u['age_days']}</strong></td>
          <td class="num">{rp(u['hpp'])}</td>
        </tr>"""
        for u in m["over_90"]
    ) or '<tr><td colspan="6" class="empty">Tidak ada unit di atas 90 hari.</td></tr>'

    dq = m["data_quality"]
    dq_rows = "".join(
        f'<tr><th scope="row">{e(k)}</th><td class="num">{n}</td></tr>'
        for k, n in sorted(dq["issues"].items(), key=lambda kv: -kv[1])
    ) or '<tr><td colspan="2" class="empty">Tidak ada temuan.</td></tr>'

    ledger = "".join(
        f"""<tr data-status="{e(u['status'] or '-')}" data-lokasi="{e(u['lokasi'] or '')}">
          <td class="mono">{e(u['no_do'])}</td>
          <td class="mono">{e(u['tanggal_do'])}</td>
          <td>{e(u['nama_mobil'])}</td>
          <td class="sub">{e(u['varian'])}</td>
          <td class="sub">{e(u['warna'])}</td>
          <td class="mono sub">{e(u['no_rangka'] or '—')}</td>
          <td>{e(u['lokasi'] or '—')}</td>
          <td class="num">{u['age_days'] if u['age_days'] is not None else '—'}</td>
          <td class="num">{rp(u['hpp'])}</td>
          <td><span class="pill p{e((u['status'] or 'none').lower().replace('-', 'none'))}">{e(u['status'] or '—')}</span></td>
        </tr>"""
        for u in m["units"]
    )

    recon = "".join(
        f"""<tr>
          <th scope="row">{e(r['label'])}</th>
          <td class="num mono">{r['claimed'] if r['claimed'] is not None else '—'}</td>
          <td class="num mono">{r['computed']}</td>
          <td class="{'ok' if r['match'] else 'crit'}">{'cocok' if r['match'] else 'selisih'}</td>
        </tr>"""
        for r in m["reconciliation"]
    )

    return f"""<title>Stok Harian DCA</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root {{
  --ground:{C['ground']}; --surface:{C['surface']}; --ink:{C['ink']}; --muted:{C['muted']};
  --line:{C['line']}; --accent:{C['accent']};
  --free:{C['free']}; --matching:{C['matching']}; --sold:{C['sold']};
  --fresh:{C['fresh']}; --warn:{C['warn']}; --crit:{C['crit']};
  --raise:0 1px 2px rgba(20,23,27,.05);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ground:#101316; --surface:#171b20; --ink:#e8ebee; --muted:#96a0ac;
    --line:#262c33; --accent:#5fb3c4;
    --free:#5fb3c4; --matching:#d8a441; --sold:#8b95a3;
    --fresh:#5cba8b; --warn:#d8a441; --crit:#e0705f;
    --raise:0 1px 2px rgba(0,0,0,.4);
  }}
}}
:root[data-theme="dark"] {{
  --ground:#101316; --surface:#171b20; --ink:#e8ebee; --muted:#96a0ac;
  --line:#262c33; --accent:#5fb3c4;
  --free:#5fb3c4; --matching:#d8a441; --sold:#8b95a3;
  --fresh:#5cba8b; --warn:#d8a441; --crit:#e0705f;
  --raise:0 1px 2px rgba(0,0,0,.4);
}}
*{{box-sizing:border-box}}
body{{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:Archivo,"Helvetica Neue",Arial,sans-serif;
  font-size:14px; line-height:1.5; -webkit-font-smoothing:antialiased;
}}
.wrap{{max-width:1180px;margin:0 auto;padding:32px 24px 72px;display:flex;flex-direction:column;gap:28px}}

.masthead{{display:flex;flex-wrap:wrap;align-items:baseline;gap:12px 20px;
  padding-bottom:18px;border-bottom:2px solid var(--ink)}}
.masthead h1{{margin:0;font-size:26px;font-weight:800;letter-spacing:-.02em;line-height:1.15}}
.masthead .sub{{font-size:13px}}
.eyebrow{{font-size:11px;font-weight:600;letter-spacing:.13em;text-transform:uppercase;
  color:var(--muted);width:100%}}
.spacer{{flex:1}}

h2{{margin:0 0 12px;font-size:12px;font-weight:600;letter-spacing:.12em;
  text-transform:uppercase;color:var(--muted)}}
section{{display:block}}
.note{{font-size:13px;color:var(--muted);max-width:68ch;margin:10px 0 0}}

.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);border-radius:3px;overflow:hidden}}
.kpi{{background:var(--surface);padding:16px 18px;display:flex;flex-direction:column;gap:5px}}
.kpi .label{{font-size:11px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}}
.kpi .value{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:30px;font-weight:600;
  letter-spacing:-.02em;font-variant-numeric:tabular-nums;line-height:1.05}}
.kpi .value.small{{font-size:20px}}
.kpi .foot{{font-size:12px;color:var(--muted)}}
.kpi.accent .value{{color:var(--accent)}}
.kpi.alarm .value{{color:var(--crit)}}

.panel{{background:var(--surface);border:1px solid var(--line);border-radius:3px;
  padding:20px;box-shadow:var(--raise)}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}}

.stack{{display:flex;height:12px;border-radius:2px;overflow:hidden;gap:1px;margin-bottom:16px}}
.seg{{min-width:3px}}

table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
thead th{{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);border-bottom:1px solid var(--ink);white-space:nowrap}}
tbody tr:last-child td,tbody tr:last-child th{{border-bottom:0}}
tbody th{{font-weight:500;white-space:nowrap}}
.num{{text-align:right;font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-variant-numeric:tabular-nums;white-space:nowrap}}
.mono{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}}
.sub{{color:var(--muted)}}
.pct{{color:var(--muted)}}
.crit{{color:var(--crit)}}
.ok{{color:var(--fresh)}}
.empty{{color:var(--muted);font-style:italic}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;
  vertical-align:baseline}}
.barcell{{width:34%;padding-right:14px}}
.bar{{display:block;height:8px;border-radius:1px;min-width:2px;opacity:.85}}

.pill{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;font-weight:600;
  letter-spacing:.03em;border:1px solid currentColor}}
.pfree{{color:var(--free)}} .pmatching{{color:var(--matching)}}
.psold{{color:var(--sold)}} .pnone{{color:var(--crit)}}

.scroll{{overflow-x:auto;max-height:560px;overflow-y:auto;border:1px solid var(--line);
  border-radius:3px;background:var(--surface)}}
.scroll table{{min-width:1020px}}
.scroll thead th{{position:sticky;top:0;background:var(--surface);z-index:1}}

.filters{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}}
.filters button{{font:inherit;font-size:12px;font-weight:500;padding:5px 13px;cursor:pointer;
  border:1px solid var(--line);border-radius:14px;background:var(--surface);color:var(--muted)}}
.filters button[aria-pressed="true"]{{border-color:var(--ink);color:var(--ink);font-weight:600}}
.filters button:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}

footer{{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:16px;
  max-width:78ch}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important;animation:none!important}}}}
</style>

<div class="wrap">
  <header class="masthead">
    <span class="eyebrow">PT. Duta Cendana Adimandiri &middot; Suzuki</span>
    <h1>Stok Harian</h1>
    <span class="spacer"></span>
    <span class="sub mono">{e(id_date(m['as_of']))}</span>
  </header>

  <section>
    <h2>Ringkasan</h2>
    <div class="kpis">
      <div class="kpi accent">
        <span class="label">Stok tersedia</span>
        <span class="value">{c['unsold']}</span>
        <span class="foot">{c['free']} free &middot; {c['matching']} matching</span>
      </div>
      <div class="kpi">
        <span class="label">Nilai stok (HPP)</span>
        <span class="value small">{e(rp_short(v['unsold_hpp']))}</span>
        <span class="foot">modal tertahan di unit belum terjual</span>
      </div>
      <div class="kpi {'alarm' if aging.get('> 90 hari', {}).get('count') else ''}">
        <span class="label">Umur &gt; 90 hari</span>
        <span class="value">{aging.get('> 90 hari', {}).get('count', 0)}</span>
        <span class="foot">{e(rp_short(v['over_90_hpp']))} tertahan</span>
      </div>
      <div class="kpi">
        <span class="label">Sudah terjual</span>
        <span class="value">{c['sold']}</span>
        <span class="foot">tercatat di tabel yang sama</span>
      </div>
      <div class="kpi {'alarm' if m['uncounted_rows'] else ''}">
        <span class="label">Tanpa status</span>
        <span class="value">{m['uncounted_rows']}</span>
        <span class="foot">tidak masuk hitungan mana pun</span>
      </div>
    </div>
  </section>

  <section>
    <h2>Umur stok</h2>
    <div class="panel">
      <div class="stack">{seg}</div>
      <table>
        <thead><tr><th>Kelompok umur</th><th class="num">Unit</th><th class="num">Porsi</th>
          <th class="num">Nilai HPP</th></tr></thead>
        <tbody>{aging_rows}</tbody>
      </table>
      <p class="note">Umur dihitung sejak tanggal DO sampai {e(id_date(m['as_of']))},
        hanya untuk unit yang belum terjual.</p>
    </div>
  </section>

  <div class="two">
    <section>
      <h2>Per model</h2>
      <div class="panel">
        <table>
          <thead><tr><th>Model</th><th></th><th class="num">Unit</th><th class="num">Free</th>
            <th class="num">Match</th><th class="num">Nilai</th></tr></thead>
          <tbody>{model_rows}</tbody>
        </table>
        <p class="note">Seluruh baris tabel sumber, termasuk unit yang sudah terjual.</p>
      </div>
    </section>
    <section>
      <h2>Stok tersedia per lokasi</h2>
      <div class="panel">
        <table>
          <thead><tr><th>Lokasi</th><th></th><th class="num">Unit</th><th class="num">Free</th>
            <th class="num">Match</th><th class="num">Nilai</th></tr></thead>
          <tbody>{loc_rows}</tbody>
        </table>
        <p class="note">Hanya unit berstatus FREE dan MATCHING.</p>
      </div>
    </section>
  </div>

  <section>
    <h2>Perlu perhatian &mdash; stok di atas 90 hari</h2>
    <div class="panel">
      <table>
        <thead><tr><th>No DO</th><th>Unit</th><th>Warna</th><th>Lokasi</th>
          <th class="num">Umur</th><th class="num">HPP</th></tr></thead>
        <tbody>{over90}</tbody>
      </table>
    </div>
  </section>

  <div class="two">
    <section>
      <h2>Rekonsiliasi angka sumber</h2>
      <div class="panel">
        <table>
          <thead><tr><th>Penghitung</th><th class="num">Email</th><th class="num">Tabel</th>
            <th>Status</th></tr></thead>
          <tbody>{recon}</tbody>
        </table>
        <p class="note">&ldquo;Total Stock&rdquo; pada email sumber menghitung FREE + MATCHING,
          bukan seluruh baris tabel. {m['rows_in_table']} baris terbaca,
          {m['placeholder_rows']} di antaranya baris placeholder tanpa nilai.</p>
      </div>
    </section>
    <section>
      <h2>Kualitas data</h2>
      <div class="panel">
        <table>
          <thead><tr><th>Temuan</th><th class="num">Baris</th></tr></thead>
          <tbody>{dq_rows}</tbody>
        </table>
        <p class="note">No DO ganda:
          <span class="mono">{e(', '.join(dq['duplicate_do']) or '—')}</span>.
          Setiap No DO ganda muncul dua kali dengan isi berbeda &mdash; satu baris lengkap dan
          satu baris tanpa lokasi/status.</p>
      </div>
    </section>
  </div>

  <section>
    <h2>Daftar unit &mdash; {m['rows_in_table']} baris</h2>
    <div class="filters" role="group" aria-label="Saring menurut status">
      <button type="button" data-f="ALL" aria-pressed="true">Semua</button>
      <button type="button" data-f="FREE" aria-pressed="false">Free</button>
      <button type="button" data-f="MATCHING" aria-pressed="false">Matching</button>
      <button type="button" data-f="SOLD" aria-pressed="false">Sold</button>
      <button type="button" data-f="-" aria-pressed="false">Tanpa status</button>
    </div>
    <div class="scroll">
      <table>
        <thead><tr><th>No DO</th><th>Tgl DO</th><th>Model</th><th>Varian</th><th>Warna</th>
          <th>No rangka</th><th>Lokasi</th><th class="num">Umur</th><th class="num">HPP</th>
          <th>Status</th></tr></thead>
        <tbody id="ledger">{ledger}</tbody>
      </table>
    </div>
  </section>

  <footer>
    Disusun otomatis dari email <em>Notifikasi Stock</em> ArUnit tertanggal
    {e(id_date(m['as_of']))}. Seluruh angka dihitung ulang dari tabel di email tersebut;
    tidak ada angka yang diketik ulang. Dibuat {e(m['generated_at'])}.
  </footer>
</div>

<script>
(function () {{
  var rows = Array.prototype.slice.call(document.querySelectorAll('#ledger tr'));
  var btns = Array.prototype.slice.call(document.querySelectorAll('.filters button'));
  btns.forEach(function (b) {{
    b.addEventListener('click', function () {{
      var f = b.dataset.f;
      btns.forEach(function (x) {{ x.setAttribute('aria-pressed', String(x === b)); }});
      rows.forEach(function (r) {{
        r.hidden = !(f === 'ALL' || r.dataset.status === f);
      }});
    }});
  }});
}})();
</script>
"""


# --------------------------------------------------------------------------
# Email body -- inline styles only, no webfonts, no script, no attachment
# --------------------------------------------------------------------------

FONT = "Helvetica Neue,Helvetica,Arial,sans-serif"
MONO = "SFMono-Regular,Menlo,Consolas,monospace"

# Reusable style fragments. Inline styles are unavoidable in email, but repeating
# the full declaration on all ~200 cells made the body 30 KB, of which 82% was
# duplicated attribute text. font-family is set once per table and inherited, and
# the cell styles below are shared constants -- the body more than halves, which
# matters because the whole document is emitted verbatim as a tool-call argument
# on every run. Same visual result, a third of the bytes.
_B = f"border-bottom:1px solid {C['line']}"
TD = f"padding:6px 10px;{_B};font-size:13px"
TDR = f"{TD};text-align:right;font-family:{MONO}"
TDM = f"{TD};font-family:{MONO}"
TH = (f"padding:6px 10px;border-bottom:2px solid {C['ink']};font-size:10px;font-weight:600;"
      f"letter-spacing:.08em;text-transform:uppercase;color:{C['muted']}")
TBL = (f"border-collapse:collapse;background:#fff;border:1px solid {C['line']};"
       f"font-family:{FONT};color:{C['ink']}")
NOTE = f"font-size:12px;line-height:1.5;color:{C['muted']}"
DASH = "\u2014"      # em dash; kept out of f-string expressions (no backslashes allowed there)
MIDDOT = "\u00b7"


def render_email(m: dict, artifact_url: str | None = None) -> str:
    c, v, aging = m["counts"], m["value"], m["aging"]
    unsold = max(c["unsold"], 1)

    def kpi(label, value, foot, color=C["ink"]):
        return (
            f'<td style="padding:14px 16px;border:1px solid {C["line"]};background:#fff;'
            f'vertical-align:top;width:25%">'
            f'<div style="font-size:10px;font-weight:600;letter-spacing:.09em;'
            f'text-transform:uppercase;color:{C["muted"]}">{e(label)}</div>'
            f'<div style="font:600 26px/1.15 {MONO};color:{color};padding:4px 0 2px">{e(value)}</div>'
            f'<div style="font-size:12px;color:{C["muted"]}">{e(foot)}</div></td>')

    kpis = (kpi("Stok tersedia", c["unsold"], f"{c['free']} free {MIDDOT} {c['matching']} matching",
                C["accent"])
            + kpi("Nilai stok (HPP)", rp_short(v["unsold_hpp"]), "modal tertahan")
            + kpi("Umur > 90 hari", aging.get("> 90 hari", {}).get("count", 0),
                  f"{rp_short(v['over_90_hpp'])} tertahan",
                  C["crit"] if aging.get("> 90 hari", {}).get("count") else C["ink"])
            + kpi("Tanpa status", m["uncounted_rows"], "perlu dilengkapi",
                  C["crit"] if m["uncounted_rows"] else C["ink"]))

    aging_rows = "".join(
        f'<tr><td style="{TD}">'
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:4px;'
        f'background:{BUCKET_COLOR.get(k, C["muted"])};margin-right:8px"></span>{e(k)}</td>'
        f'<td style="{TDR}">{d["count"]}</td>'
        f'<td style="{TDR};color:{C["muted"]}">{d["count"] / unsold * 100:.0f}%</td>'
        f'<td style="{TDR}">{rp(d["value"])}</td></tr>'
        for k, d in aging.items() if d["count"])

    def group_rows(items):
        return "".join(
            f'<tr><td style="{TD}">{e(k)}</td>'
            f'<td style="{TDR}">{r["count"]}</td>'
            f'<td style="{TDR}">{r["free"]}</td>'
            f'<td style="{TDR}">{r["matching"]}</td>'
            f'<td style="{TDR}">{rp(r["value"])}</td></tr>'
            for k, r in items)

    loc_rows = group_rows(m["by_location"].items())
    model_rows = group_rows(m["by_model"].items())

    over90 = "".join(
        f'<tr><td style="{TDM}">{e(u["no_do"])}</td>'
        f'<td style="{TD}">{e(u["nama_mobil"])} '
        f'<span style="color:{C["muted"]}">{e(u["varian"])}</span></td>'
        f'<td style="{TD}">{e(u["lokasi"] or DASH)}</td>'
        f'<td style="{TDR};font-weight:600;color:{C["crit"]}">{u["age_days"]}</td>'
        f'<td style="{TDR}">{rp(u["hpp"])}</td></tr>'
        for u in m["over_90"]
    ) or f'<tr><td colspan="5" style="{TD};font-style:italic;color:{C["muted"]}">Tidak ada unit di atas 90 hari.</td></tr>'

    dq = m["data_quality"]
    dq_items = "".join(
        f'<li style="margin-bottom:3px">{e(k)} &mdash; <strong>{n}</strong> baris</li>'
        for k, n in sorted(dq["issues"].items(), key=lambda kv: -kv[1]))
    dup = ", ".join(dq["duplicate_do"])

    def h2(t):
        return (f'<div style="font-size:11px;font-weight:600;letter-spacing:.12em;'
                f'text-transform:uppercase;color:{C["muted"]};padding:26px 0 8px">{e(t)}</div>')

    def thead(cells):
        return "<tr>" + "".join(
            f'<th style="{TH};text-align:{"right" if right else "left"}">{e(t)}</th>'
            for t, right in cells) + "</tr>"

    def table(cells, rows):
        return (f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
                f'style="{TBL}"><thead>{thead(cells)}</thead><tbody>{rows}</tbody></table>')

    link = ""
    if artifact_url:
        link = (f'<p style="font-size:13px;line-height:1.6;color:{C["muted"]};margin:18px 0 0">'
                f'Versi dasbor lengkap, dapat disaring per status: '
                f'<a href="{e(artifact_url)}" style="color:{C["accent"]}">buka dasbor</a>.</p>')

    return f"""<div style="background:{C['ground']};padding:24px 12px;font-family:{FONT};\
color:{C['ink']};font-size:14px;line-height:1.5">
<div style="max-width:820px;margin:0 auto">

  <div style="border-bottom:2px solid {C['ink']};padding-bottom:14px">
    <div style="font-size:10px;font-weight:600;letter-spacing:.13em;text-transform:uppercase;
      color:{C['muted']}">PT. Duta Cendana Adimandiri &middot; Suzuki</div>
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%"
      style="font-family:{FONT}"><tr>
      <td style="font-size:24px;font-weight:800;letter-spacing:-.02em;padding-top:4px">Stok Harian</td>
      <td style="font-family:{MONO};font-size:13px;color:{C['muted']};text-align:right;
        vertical-align:bottom">{e(id_date(m['as_of']))}</td>
    </tr></table>
  </div>

  <table role="presentation" cellpadding="0" cellspacing="0" width="100%"
    style="border-collapse:collapse;margin-top:18px;font-family:{FONT}"><tr>{kpis}</tr></table>

  {h2('Umur stok')}
  {table([('Kelompok umur', False), ('Unit', True), ('Porsi', True), ('Nilai HPP', True)], aging_rows)}
  <p style="{NOTE};margin:8px 0 0">Dihitung sejak tanggal DO sampai
    {e(id_date(m['as_of']))}, hanya unit yang belum terjual.</p>

  {h2('Perlu perhatian — stok di atas 90 hari')}
  {table([('No DO', False), ('Unit', False), ('Lokasi', False), ('Umur', True), ('HPP', True)], over90)}

  {h2('Stok tersedia per lokasi')}
  {table([('Lokasi', False), ('Unit', True), ('Free', True), ('Match', True), ('Nilai HPP', True)], loc_rows)}

  {h2('Per model')}
  {table([('Model', False), ('Unit', True), ('Free', True), ('Match', True), ('Nilai HPP', True)], model_rows)}

  {h2('Catatan kualitas data')}
  <div style="background:#fff;border:1px solid {C['line']};padding:14px 16px">
    <ul style="font-size:13px;line-height:1.6;margin:0;padding-left:18px">{dq_items}</ul>
    <p style="{NOTE};margin:10px 0 0">
      &ldquo;Total Stock&rdquo; pada email sumber menghitung FREE + MATCHING
      ({c['unsold']} unit), bukan seluruh {m['rows_in_table']} baris tabel.
      {m['uncounted_rows']} baris tidak berstatus sehingga tidak terhitung di mana pun.
      No DO ganda: <span style="font-family:{MONO}">{e(dup or DASH)}</span>.</p>
  </div>
  {link}

  <p style="{NOTE};border-top:1px solid {C['line']};padding-top:14px;margin-top:28px">
    Disusun otomatis dari email <em>Notifikasi Stock</em> ArUnit tertanggal
    {e(id_date(m['as_of']))}. Seluruh angka dihitung ulang dari tabel pada email tersebut.
    Daftar unit lengkap tetap tersedia di email ArUnit asli.</p>

</div></div>"""


if __name__ == "__main__":
    metrics = json.load(open(sys.argv[1], encoding="utf-8"))
    url = sys.argv[2] if len(sys.argv) > 2 else None
    open("out/artifact.html", "w", encoding="utf-8").write(render_artifact(metrics))
    open("out/email.html", "w", encoding="utf-8").write(render_email(metrics, url))
    print("wrote out/artifact.html and out/email.html")
