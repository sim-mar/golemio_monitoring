"""
Čte kasparovo_namesti_odpady.csv a generuje index.html s grafy.
Spouští se automaticky z collect_data.py po každém sběru.
"""

import csv
import json
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE   = os.path.join(SCRIPT_DIR, "kasparovo_namesti_odpady.csv")
HTML_FILE  = os.path.join(SCRIPT_DIR, "index.html")

COLORS = {
    "Papír":                 {"line": "#e2e8f0", "fill": "rgba(226,232,240,0.08)"},
    "Multikomoditní sběr":   {"line": "#a78bfa", "fill": "rgba(167,139,250,0.12)"},
    "Kovy":                  {"line": "#fbbf24", "fill": "rgba(251,191,36,0.12)"},
    "Barevné sklo":          {"line": "#60a5fa", "fill": "rgba(96,165,250,0.12)"},
}
def icon(color: str) -> str:
    return f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};flex-shrink:0"></span>'
ORDER = ["Papír", "Multikomoditní sběr", "Kovy", "Barevné sklo"]


DAYS_CZ = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]

def parse_csv(path: str) -> tuple[dict, dict]:
    """Vrátí (series, meta) kde:
    series = {druh: [(measured_at_utc, pct), ...]}
    meta   = {druh: {dalsi_svoz, dny_svozu}}
    """
    series: dict[str, list] = {k: [] for k in ORDER}
    meta:   dict[str, dict] = {k: {"dalsi_svoz": "", "dny_svozu": "", "posledni_svoz": "", "predikce": ""} for k in ORDER}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("stanice_id") or row[0].startswith("collected_at"):
                continue
            try:
                if row[0].isdigit():
                    # Format 1: ruční záznamy
                    druh          = row[9]
                    pct           = int(row[11])
                    ts            = row[12]
                    predikce      = row[13] if len(row) > 13 else ""
                    posledni_svoz = row[14] if len(row) > 14 else ""
                    dny_svozu     = row[16] if len(row) > 16 else ""
                    dalsi_svoz    = row[17] if len(row) > 17 else ""
                else:
                    # Format 2: collector
                    druh          = row[5]
                    pct           = int(row[6])
                    ts            = row[7]
                    predikce      = row[8]  if len(row) > 8  else ""
                    posledni_svoz = row[9]  if len(row) > 9  else ""
                    dny_svozu     = ""
                    dalsi_svoz    = row[10] if len(row) > 10 else ""
            except (IndexError, ValueError):
                continue

            if druh in series:
                series[druh].append((ts, pct))
                if dalsi_svoz:    meta[druh]["dalsi_svoz"]    = dalsi_svoz
                if dny_svozu:     meta[druh]["dny_svozu"]     = dny_svozu
                if posledni_svoz: meta[druh]["posledni_svoz"] = posledni_svoz
                if predikce:      meta[druh]["predikce"]      = predikce

    def norm_ts(ts: str) -> str:
        """Normalizuje timestamp — odstraní .000 před Z pro správný dedup."""
        return ts.replace(".000Z", "Z").replace(".000+", "+")

    # Seřadit dle timestampu, deduplikovat
    for druh in series:
        seen = set()
        unique = []
        for ts, pct in sorted(series[druh], key=lambda x: x[0]):
            key = norm_ts(ts)
            if key not in seen:
                seen.add(key)
                unique.append((norm_ts(ts), pct))
        series[druh] = unique

    return series, meta


def fmt_ts(ts: str) -> str:
    """ISO timestamp → čitelný čas CET."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        offset = 2  # CEST (od posledního března)
        h = (dt.hour + offset) % 24
        return f"{dt.day}.{dt.month}. {h:02d}:{dt.minute:02d}"
    except Exception:
        return ts


def days_since(ts: str) -> str:
    """Počet dní od daného timestampu do dnes."""
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        d  = (datetime.now(timezone.utc) - dt).days
        return f"{d} {'den' if d == 1 else 'dny' if 2 <= d <= 4 else 'dní'}"
    except Exception:
        return "—"


def fmt_date(ts: str) -> str:
    """ISO datum → krátký formát d.m."""
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return f"{dt.day}.{dt.month}."
    except Exception:
        return ts


def predikce_cell(predikce: str, dalsi_svoz: str) -> str:
    """Predikce přetečení s ikonou varování pokud je dřív než svoz."""
    if not predikce:
        return "—"
    try:
        dt_pred = datetime.fromisoformat(predikce.replace("Z", "+00:00"))
        now     = datetime.now(timezone.utc)
        label   = f"{dt_pred.day}.{dt_pred.month}."
        if dt_pred < now:
            return f'<span style="color:var(--danger)">{label} 🔴</span>'
        if dalsi_svoz:
            dt_svoz = datetime.fromisoformat(dalsi_svoz + "T00:00:00+00:00")
            if dt_pred < dt_svoz:
                return f'<span style="color:var(--warning)">{label} ⚠️</span>'
        return label
    except Exception:
        return "—"


def fmt_svoz(dalsi_svoz: str, dny_svozu: str) -> str:
    """Formátuje datum příštího svozu s dnem v týdnu."""
    if not dalsi_svoz:
        return "—"
    try:
        d = datetime.fromisoformat(dalsi_svoz)
        den = DAYS_CZ[d.weekday()]
        label = f"{den} {d.day}.{d.month}.{d.year}"
        if dny_svozu:
            label += f" <span style='color:var(--muted)'>({dny_svozu})</span>"
        return label
    except Exception:
        return dalsi_svoz


def build(series: dict, meta: dict) -> str:
    dt  = datetime.now(timezone.utc)
    h_local = (dt.hour + 2) % 24
    now = f"{dt.day}. {dt.month}. {dt.year} {h_local:02d}:{dt.minute:02d}"

    # Aktuální hodnoty (poslední záznam)
    latest = {}
    for druh, pts in series.items():
        latest[druh] = pts[-1][1] if pts else None

    # JS data pro line chart — společná osa X (unikátní timestampy všech senzorů)
    all_ts = sorted({ts for pts in series.values() for ts, _ in pts})
    labels_js = json.dumps([fmt_ts(ts) for ts in all_ts])

    LABELS = {
        "Papír": "Papír",
        "Multikomoditní sběr": "Multikomoditní",
        "Kovy": "Kovy",
        "Barevné sklo": "Barevné sklo",
    }
    datasets_js = []
    for druh in ORDER:
        pts_map = {ts: pct for ts, pct in series.get(druh, [])}
        data = [pts_map.get(ts, "null") for ts in all_ts]
        c = COLORS.get(druh, {"line": "#fff", "fill": "rgba(255,255,255,0.1)"})
        datasets_js.append(f"""{{
            label: {json.dumps(LABELS[druh])},
            data: {json.dumps(data)},
            borderColor: "{c['line']}",
            backgroundColor: "{c['fill']}",
            pointBackgroundColor: "{c['line']}",
            pointRadius: 5,
            pointHoverRadius: 7,
            pointStyle: 'circle',
            borderWidth: 2.5,
            tension: 0.3,
            fill: false,
            spanGaps: true
        }}""")
    datasets_str = ",\n".join(datasets_js)

    def gauge_color(v):
        if v is None: return "#7a8aaa"
        if v >= 90: return "#f87171"
        if v >= 60: return "#fbbf24"
        return "#34d399"

    def status_badge(v):
        if v is None: return '<span class="badge badge-ok">Neznámý</span>'
        if v >= 90: return '<span class="badge badge-danger">Kritické</span>'
        if v >= 60: return '<span class="badge badge-warning">Pozor</span>'
        return '<span class="badge badge-ok">OK</span>'

    def donut_js(canvas_id, pct, color):
        col = gauge_color(pct)
        return f"""new Chart(document.getElementById('{canvas_id}'), {{
            type: 'doughnut',
            data: {{
                datasets: [{{
                    data: [{pct}, {100 - pct}],
                    backgroundColor: ['{color}', 'rgba(255,255,255,0.06)'],
                    borderWidth: 0
                }}]
            }},
            options: {{ cutout: '74%', responsive: true, plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }} }} }},
            plugins: [{{
                id: 'ct',
                beforeDraw(ch) {{
                    const {{width: w, height: h, ctx}} = ch;
                    ctx.save();
                    ctx.font = `800 ${{Math.min(w,h)*0.24}}px Segoe UI`;
                    ctx.textBaseline = 'middle'; ctx.textAlign = 'center';
                    ctx.fillStyle = '{col}';
                    ctx.fillText('{pct}%', w/2, h/2);
                    ctx.restore();
                }}
            }}]
        }});"""

    p_pct  = latest.get("Papír", 0) or 0
    m_pct  = latest.get("Multikomoditní sběr", 0) or 0
    k_pct  = latest.get("Kovy", 0) or 0
    s_pct  = latest.get("Barevné sklo", 0) or 0

    html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Monitoring odpadů — Kašparovo náměstí 350/1</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --bg:#0b0f1a; --surface:#131929; --card:#1a2236; --border:#253050;
      --accent:#00b4d8; --accent2:#0077b6;
      --text:#e8edf5; --muted:#7a8aaa;
      --success:#34d399; --warning:#fbbf24; --danger:#f87171;
      --radius:12px; --shadow:0 4px 24px rgba(0,0,0,.45);
    }}
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;line-height:1.6}}

    header{{background:var(--surface);border-bottom:1px solid var(--border);padding:0 2rem;display:flex;align-items:center;justify-content:space-between;height:64px;position:sticky;top:0;z-index:100}}
    .logo{{display:flex;align-items:center;gap:.75rem;font-size:1.1rem;font-weight:700;color:var(--accent);letter-spacing:.02em}}
    .logo svg{{width:32px;height:32px}}
    .header-meta{{font-size:.8rem;color:var(--muted);text-align:right;margin-left:auto}}
    .header-meta strong{{color:var(--text)}}

    .hero{{background:linear-gradient(135deg,var(--accent2) 0%,var(--bg) 60%);padding:2.5rem 2rem 2rem}}
    .hero-inner{{max-width:1200px;margin:0 auto}}
    .hero h1{{font-size:clamp(1.5rem,3vw,2.2rem);font-weight:800;margin-bottom:.4rem;letter-spacing:-.02em}}
    .hero-sub{{color:rgba(232,237,245,.7);font-size:.95rem;display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap}}
    .tag{{background:rgba(0,180,216,.15);border:1px solid rgba(0,180,216,.35);color:var(--accent);padding:.2rem .7rem;border-radius:20px;font-size:.75rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase}}

    main{{max-width:1200px;margin:0 auto;padding:2rem 2rem 4rem}}

    .section-head{{display:flex;align-items:center;gap:.75rem;margin-bottom:1.25rem}}
    .section-head h2{{font-size:1.05rem;font-weight:700}}
    .section-head .line{{flex:1;height:1px;background:var(--border)}}

    /* ── DONUT ROW ── */
    .donuts-row{{display:flex;gap:1rem;margin-bottom:2.5rem;flex-wrap:wrap}}
    .donut-card{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:1rem 1.25rem;flex:1;min-width:180px;display:flex;flex-direction:column;align-items:center;gap:.5rem;box-shadow:var(--shadow)}}
    .donut-label{{font-size:.95rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--text);display:flex;align-items:center;gap:.4rem}}
    .donut-canvas{{width:100px!important;height:100px!important}}
    .donut-meta{{font-size:.72rem;color:var(--muted);text-align:center;line-height:1.4}}
    .donut-info{{font-size:.71rem;color:var(--muted);text-align:left;line-height:1.9;width:100%;border-top:1px solid var(--border);padding-top:.5rem;margin-top:.25rem}}

    /* ── LINE CHART ── */
    .chart-card{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:1.5rem;box-shadow:var(--shadow);margin-bottom:2.5rem}}

    /* ── TABLE ── */
    .table-wrap{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow);margin-bottom:2rem}}
    table{{width:100%;border-collapse:collapse;font-size:.88rem}}
    thead tr{{background:rgba(0,180,216,.08);border-bottom:1px solid var(--border)}}
    th{{padding:.85rem 1.25rem;text-align:left;font-size:.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}}
    td{{padding:.8rem 1.25rem;border-bottom:1px solid rgba(37,48,80,.6);vertical-align:middle}}
    tbody tr:last-child td{{border-bottom:none}}
    tbody tr:hover{{background:rgba(255,255,255,.025)}}
    .badge{{display:inline-block;padding:.2rem .65rem;border-radius:6px;font-size:.75rem;font-weight:700}}
    .badge-danger{{background:rgba(248,113,113,.18);color:var(--danger)}}
    .badge-warning{{background:rgba(251,191,36,.18);color:var(--warning)}}
    .badge-ok{{background:rgba(52,211,153,.18);color:var(--success)}}
    .mini-bar-track{{width:100px;height:7px;background:rgba(255,255,255,.07);border-radius:4px;overflow:hidden;display:inline-block;vertical-align:middle;margin-left:.5rem}}
    .mini-bar-fill{{height:100%;border-radius:4px}}

    .info-box{{background:rgba(0,119,182,.1);border:1px solid rgba(0,119,182,.35);border-radius:var(--radius);padding:.9rem 1.25rem;font-size:.83rem;color:rgba(232,237,245,.7);margin-bottom:2rem}}
    .info-box strong{{color:var(--accent)}}

    footer{{background:var(--surface);border-top:1px solid var(--border);padding:1.25rem 2rem;text-align:center;font-size:.78rem;color:var(--muted)}}
    footer a{{color:var(--accent);text-decoration:none}}
  </style>
</head>
<body>

<header>
  <div class="header-meta"><strong>Golemio API</strong> · Praha-8<br>Generováno: {now}</div>
</header>

<div class="hero">
  <div class="hero-inner">
    <h1>Kašparovo náměstí 350/1</h1>
    <div class="hero-sub">
      <span>📍 Praha 8 · Stanice č. 0008/067</span>
      <span class="tag">Sensoneo</span>
      <span class="tag">4 nádoby</span>
      <span class="tag">{len(all_ts)} měření</span>
    </div>
  </div>
</div>

<main>

  <!-- DONUT CHARTS -->
  <div class="section-head"><h2>Aktuální zaplnění</h2><div class="line"></div></div>
  <div class="donuts-row">
    <div class="donut-card">
      <div class="donut-label">{icon(COLORS['Papír']['line'])} Papír</div>
      <canvas id="dPapir" class="donut-canvas"></canvas>
      <div class="donut-meta">{status_badge(p_pct)}</div>
      <div class="donut-info">
        <div>⏱ {fmt_ts(series["Papír"][-1][0]) if series["Papír"] else "—"}</div>
        <div>🚛 {fmt_svoz(meta["Papír"]["dalsi_svoz"], meta["Papír"]["dny_svozu"])}</div>
      </div>
    </div>
    <div class="donut-card">
      <div class="donut-label">{icon(COLORS['Multikomoditní sběr']['line'])} Multikomoditní</div>
      <canvas id="dMulti" class="donut-canvas"></canvas>
      <div class="donut-meta">{status_badge(m_pct)}</div>
      <div class="donut-info">
        <div>⏱ {fmt_ts(series["Multikomoditní sběr"][-1][0]) if series["Multikomoditní sběr"] else "—"}</div>
        <div>🚛 {fmt_svoz(meta["Multikomoditní sběr"]["dalsi_svoz"], meta["Multikomoditní sběr"]["dny_svozu"])}</div>
      </div>
    </div>
    <div class="donut-card">
      <div class="donut-label">{icon(COLORS['Kovy']['line'])} Kovy</div>
      <canvas id="dKovy" class="donut-canvas"></canvas>
      <div class="donut-meta">{status_badge(k_pct)}</div>
      <div class="donut-info">
        <div>⏱ {fmt_ts(series["Kovy"][-1][0]) if series["Kovy"] else "—"}</div>
        <div>🚛 {fmt_svoz(meta["Kovy"]["dalsi_svoz"], meta["Kovy"]["dny_svozu"])}</div>
      </div>
    </div>
    <div class="donut-card">
      <div class="donut-label">{icon(COLORS['Barevné sklo']['line'])} Barevné sklo</div>
      <canvas id="dSklo" class="donut-canvas"></canvas>
      <div class="donut-meta">{status_badge(s_pct)}</div>
      <div class="donut-info">
        <div>⏱ {fmt_ts(series["Barevné sklo"][-1][0]) if series["Barevné sklo"] else "—"}</div>
        <div>🚛 {fmt_svoz(meta["Barevné sklo"]["dalsi_svoz"], meta["Barevné sklo"]["dny_svozu"])}</div>
      </div>
    </div>
  </div>

  <!-- LINE CHART -->
  <div class="section-head"><h2>Průběh zaplnění v čase</h2><div class="line"></div></div>
  <div class="chart-card">
    <canvas id="lineChart" height="90"></canvas>
  </div>

  <!-- TABLE -->
  <div class="section-head"><h2>Detail nádob</h2><div class="line"></div></div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>Odpad</th><th>Posl. svoz</th><th>Dní od svozu</th>
        <th>Příští svoz</th><th>Predikce přetečení</th><th>Stav</th>
      </tr></thead>
      <tbody>
        <tr>
          <td><strong style="display:flex;align-items:center;gap:.5rem">{icon(COLORS['Papír']['line'])} Papír</strong></td>
          <td>{fmt_date(meta["Papír"]["posledni_svoz"])}</td>
          <td>{days_since(meta["Papír"]["posledni_svoz"])}</td>
          <td>{fmt_svoz(meta["Papír"]["dalsi_svoz"], meta["Papír"]["dny_svozu"])}</td>
          <td>{predikce_cell(meta["Papír"]["predikce"], meta["Papír"]["dalsi_svoz"])}</td>
          <td>{status_badge(p_pct)}</td>
        </tr>
        <tr>
          <td><strong style="display:flex;align-items:center;gap:.5rem">{icon(COLORS['Multikomoditní sběr']['line'])} Multikomoditní</strong></td>
          <td>{fmt_date(meta["Multikomoditní sběr"]["posledni_svoz"])}</td>
          <td>{days_since(meta["Multikomoditní sběr"]["posledni_svoz"])}</td>
          <td>{fmt_svoz(meta["Multikomoditní sběr"]["dalsi_svoz"], meta["Multikomoditní sběr"]["dny_svozu"])}</td>
          <td>{predikce_cell(meta["Multikomoditní sběr"]["predikce"], meta["Multikomoditní sběr"]["dalsi_svoz"])}</td>
          <td>{status_badge(m_pct)}</td>
        </tr>
        <tr>
          <td><strong style="display:flex;align-items:center;gap:.5rem">{icon(COLORS['Kovy']['line'])} Kovy</strong></td>
          <td>{fmt_date(meta["Kovy"]["posledni_svoz"])}</td>
          <td>{days_since(meta["Kovy"]["posledni_svoz"])}</td>
          <td>{fmt_svoz(meta["Kovy"]["dalsi_svoz"], meta["Kovy"]["dny_svozu"])}</td>
          <td>{predikce_cell(meta["Kovy"]["predikce"], meta["Kovy"]["dalsi_svoz"])}</td>
          <td>{status_badge(k_pct)}</td>
        </tr>
        <tr>
          <td><strong style="display:flex;align-items:center;gap:.5rem">{icon(COLORS['Barevné sklo']['line'])} Barevné sklo</strong></td>
          <td>{fmt_date(meta["Barevné sklo"]["posledni_svoz"])}</td>
          <td>{days_since(meta["Barevné sklo"]["posledni_svoz"])}</td>
          <td>{fmt_svoz(meta["Barevné sklo"]["dalsi_svoz"], meta["Barevné sklo"]["dny_svozu"])}</td>
          <td>{predikce_cell(meta["Barevné sklo"]["predikce"], meta["Barevné sklo"]["dalsi_svoz"])}</td>
          <td>{status_badge(s_pct)}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="info-box">
    <strong>Data:</strong> Golemio Open Data API v2 · Stanice 5262 · Senzory Sensoneo ·
    Sběr každou hodinu (07:00–00:00 CEST) automaticky přes GitHub Actions.
  </div>

</main>

<footer>
  <a href="https://golemio.cz" target="_blank">Golemio API</a> ·
  Kašparovo náměstí 350/1, Praha 8 · Generováno {now}
</footer>

<script>
const labels   = {labels_js};
const datasets = [{datasets_str}];

// Line chart
new Chart(document.getElementById('lineChart'), {{
    type: 'line',
    data: {{ labels, datasets }},
    options: {{
        responsive: true,
        interaction: {{ mode: 'index', intersect: false }},
        scales: {{
            x: {{
                grid: {{ color: 'rgba(255,255,255,.05)' }},
                ticks: {{
                    color: '#7a8aaa',
                    font: {{ size: 11 }},
                    maxRotation: 45,
                    autoSkip: true,
                    maxTicksLimit: 12
                }}
            }},
            y: {{
                min: 0, max: 100,
                grid: {{ color: 'rgba(255,255,255,.05)' }},
                ticks: {{ color: '#7a8aaa', callback: v => v + ' %' }}
            }}
        }},
        plugins: {{
            legend: {{
                labels: {{
                    color: '#e8edf5',
                    font: {{ size: 12 }},
                    usePointStyle: true,
                    pointStyleWidth: 10
                }}
            }},
            tooltip: {{
                backgroundColor: '#1a2236',
                borderColor: '#253050',
                borderWidth: 1,
                titleColor: '#e8edf5',
                bodyColor: '#7a8aaa',
                callbacks: {{ label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.parsed.y}} %` }}
            }}
        }}
    }}
}});

// Donut charts
{donut_js("dPapir", p_pct, COLORS["Papír"]["line"])}
{donut_js("dMulti", m_pct, COLORS["Multikomoditní sběr"]["line"])}
{donut_js("dKovy", k_pct, COLORS["Kovy"]["line"])}
{donut_js("dSklo", s_pct, COLORS["Barevné sklo"]["line"])}
</script>
</body>
</html>"""
    return html


def main():
    series, meta = parse_csv(CSV_FILE)
    html = build(series, meta)
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    total = sum(len(v) for v in series.values())
    print(f"index.html vygenerován ({total} datových bodů)")


if __name__ == "__main__":
    main()
