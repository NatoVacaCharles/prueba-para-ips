#!/usr/bin/env python3
"""
generate_burndown.py — Dinosaur Exploder | IPS 2026-A
Genera un Burndown Chart HTML a partir de los Issues de GitHub.

Uso:
  python3 scripts/generate_burndown.py \
    --token "$GITHUB_TOKEN" \
    --repo "tu-usuario/dinosaur-exploder" \
    --sprint-start "2026-05-13" \
    --sprint-end "2026-05-27" \
    --total-points "28" \
    --output "docs/burndown.html"
"""

import argparse
import json
import math
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from dateutil import parser as date_parser


def fetch_issues(token: str, repo: str, label: str = "sprint: 1") -> list[dict]:
    """Obtiene todos los issues (abiertos y cerrados) con el label del sprint."""
    issues = []
    page = 1

    for state in ["closed", "open"]:
        page = 1
        while True:
            url = (
                f"https://api.github.com/repos/{repo}/issues"
                f"?state={state}&labels={urllib.parse.quote(label)}"
                f"&per_page=100&page={page}"
            )
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {token}")
            req.add_header("Accept", "application/vnd.github.v3+json")
            req.add_header("User-Agent", "burndown-generator/1.0")

            try:
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                    if not data:
                        break
                    issues.extend(data)
                    page += 1
            except urllib.error.HTTPError as e:
                print(f"Advertencia: Error al obtener issues ({state}, pág {page}): {e}")
                break

    return issues


def extract_points(issue: dict) -> int:
    """Extrae los puntos de historia del issue (desde etiquetas o título)."""
    labels = [l["name"].lower() for l in issue.get("labels", [])]
    for lbl in labels:
        for pt in [1, 2, 3, 5, 8, 13, 21]:
            if f"{pt}pt" in lbl or f"{pt} pt" in lbl or f"points: {pt}" in lbl:
                return pt
    # Fallback: cada issue vale 1 punto si no tiene etiqueta de puntos
    return 1


def build_burndown_data(
    issues: list[dict],
    sprint_start: datetime,
    sprint_end: datetime,
    total_points: int
) -> tuple[list[str], list[float], list[float]]:
    """Calcula los puntos pendientes por día."""
    days = []
    current = sprint_start
    while current <= sprint_end:
        days.append(current)
        current += timedelta(days=1)

    # Línea ideal: decrece linealmente de total_points a 0
    ideal = [
        total_points - (total_points * i / (len(days) - 1))
        for i in range(len(days))
    ]

    # Línea real: puntos cerrados por día
    closed_by_day = {d.date(): 0 for d in days}
    today = datetime.now(timezone.utc).date()

    for issue in issues:
        if issue.get("state") == "closed" and issue.get("closed_at"):
            try:
                closed_dt = date_parser.parse(issue["closed_at"]).date()
                if sprint_start.date() <= closed_dt <= sprint_end.date():
                    points = extract_points(issue)
                    closed_by_day[closed_dt] = closed_by_day.get(closed_dt, 0) + points
            except Exception:
                pass

    real = []
    remaining = total_points
    for d in days:
        if d.date() <= today:
            remaining -= closed_by_day.get(d.date(), 0)
            real.append(max(0, remaining))
        else:
            real.append(None)  # Días futuros: sin dato

    labels = [d.strftime("%d %b") for d in days]
    return labels, ideal, real


def generate_html(
    labels: list[str],
    ideal: list[float],
    real: list[float | None],
    sprint_name: str,
    total_points: int,
    closed_count: int,
    open_count: int
) -> str:
    """Genera el HTML completo con el burndown chart usando Chart.js."""

    real_js = json.dumps([r if r is not None else "null" for r in real])
    ideal_js = json.dumps([round(v, 1) for v in ideal])
    labels_js = json.dumps(labels)
    done_pts = total_points - (real[-1] if real[-1] is not None else total_points)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Burndown Chart — {sprint_name} | IPS 2026-A</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0a0a0f; --bg2: #12121a; --bg3: #1a1a26;
    --accent: #7fff6f; --accent2: #4fc3f7; --accent3: #ff6b6b;
    --text: #e8e8f0; --muted: #8888a8; --border: rgba(127,255,111,0.15);
    --mono: 'Courier New', monospace; --sans: system-ui, sans-serif;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: var(--sans); padding: 2rem; }}
  body::before {{
    content: '';
    position: fixed; inset: 0;
    background-image: linear-gradient(rgba(127,255,111,0.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(127,255,111,0.025) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none; z-index: 0;
  }}
  .container {{ position: relative; z-index: 1; max-width: 960px; margin: 0 auto; }}
  .header {{ margin-bottom: 2rem; }}
  .tag {{ font-family: var(--mono); font-size: 11px; letter-spacing: 0.15em;
    color: var(--accent); background: rgba(127,255,111,0.08);
    border: 1px solid var(--border); padding: 0.3rem 0.8rem;
    display: inline-block; margin-bottom: 1rem; }}
  h1 {{ font-family: var(--mono); font-size: 1.8rem; font-weight: 700; margin-bottom: 0.5rem; }}
  h1 span {{ color: var(--accent); }}
  .subtitle {{ color: var(--muted); font-size: 0.9rem; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px;
    background: var(--border); border: 1px solid var(--border); margin: 2rem 0; }}
  .stat {{ background: var(--bg2); padding: 1.25rem; text-align: center; }}
  .stat-num {{ font-family: var(--mono); font-size: 1.8rem; font-weight: 700;
    color: var(--accent); display: block; }}
  .stat-label {{ font-size: 11px; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.1em; margin-top: 0.25rem; }}
  .chart-wrap {{ background: var(--bg2); border: 1px solid var(--border); padding: 1.5rem; }}
  .chart-title {{ font-family: var(--mono); font-size: 12px; color: var(--accent);
    text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1rem; }}
  canvas {{ max-height: 400px; }}
  .legend {{ display: flex; gap: 2rem; margin-top: 1rem; flex-wrap: wrap; }}
  .leg-item {{ display: flex; align-items: center; gap: 0.5rem; font-size: 13px; color: var(--muted); }}
  .leg-dot {{ width: 12px; height: 3px; border-radius: 1px; }}
  .footer {{ margin-top: 1.5rem; font-family: var(--mono); font-size: 11px;
    color: var(--muted); text-align: center; padding-top: 1rem;
    border-top: 1px solid var(--border); }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="tag">IPS 2026-A · UNSA · AREQUIPA</div>
    <h1>BURNDOWN <span>CHART</span></h1>
    <p class="subtitle">{sprint_name} — Dinosaur Exploder | Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')} UTC</p>
  </div>

  <div class="stats">
    <div class="stat">
      <span class="stat-num">{total_points}</span>
      <div class="stat-label">Story Points totales</div>
    </div>
    <div class="stat">
      <span class="stat-num">{int(done_pts)}</span>
      <div class="stat-label">Puntos completados</div>
    </div>
    <div class="stat">
      <span class="stat-num">{open_count}</span>
      <div class="stat-label">Issues pendientes</div>
    </div>
    <div class="stat">
      <span class="stat-num">{closed_count}</span>
      <div class="stat-label">Issues cerrados</div>
    </div>
  </div>

  <div class="chart-wrap">
    <div class="chart-title">// Story Points restantes por día</div>
    <canvas id="burndown"></canvas>
    <div class="legend">
      <div class="leg-item"><div class="leg-dot" style="background:#4fc3f7"></div> Progreso ideal</div>
      <div class="leg-item"><div class="leg-dot" style="background:#7fff6f"></div> Progreso real</div>
    </div>
  </div>

  <div class="footer">
    Generado automáticamente por GitHub Actions · {sprint_name} · IPS 2026-A · UNSA
  </div>
</div>

<script>
const ctx = document.getElementById('burndown').getContext('2d');
new Chart(ctx, {{
  type: 'line',
  data: {{
    labels: {labels_js},
    datasets: [
      {{
        label: 'Ideal',
        data: {ideal_js},
        borderColor: '#4fc3f7',
        backgroundColor: 'rgba(79,195,247,0.05)',
        borderWidth: 2,
        borderDash: [6, 4],
        pointRadius: 0,
        fill: false,
        tension: 0
      }},
      {{
        label: 'Real',
        data: {real_js},
        borderColor: '#7fff6f',
        backgroundColor: 'rgba(127,255,111,0.08)',
        borderWidth: 2.5,
        pointRadius: 4,
        pointBackgroundColor: '#7fff6f',
        fill: true,
        tension: 0.3,
        spanGaps: false
      }}
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        backgroundColor: '#12121a',
        borderColor: 'rgba(127,255,111,0.3)',
        borderWidth: 1,
        titleColor: '#7fff6f',
        bodyColor: '#e8e8f0',
        callbacks: {{
          label: ctx => `${{ctx.dataset.label}}: ${{ctx.parsed.y !== null ? ctx.parsed.y + ' pts' : 'sin dato'}}`
        }}
      }}
    }},
    scales: {{
      x: {{
        grid: {{ color: 'rgba(127,255,111,0.05)' }},
        ticks: {{ color: '#8888a8', font: {{ family: 'Courier New', size: 11 }} }}
      }},
      y: {{
        min: 0,
        max: {total_points + 2},
        grid: {{ color: 'rgba(127,255,111,0.05)' }},
        ticks: {{ color: '#8888a8', font: {{ family: 'Courier New', size: 11 }},
          callback: v => v + ' pts' }}
      }}
    }}
  }}
}});
</script>
</body>
</html>"""


def main():
    import urllib.parse

    ap = argparse.ArgumentParser(description="Genera un Burndown Chart HTML")
    ap.add_argument("--token", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--sprint-start", required=True)
    ap.add_argument("--sprint-end", required=True)
    ap.add_argument("--total-points", type=int, required=True)
    ap.add_argument("--sprint-name", default="Sprint 1")
    ap.add_argument("--label", default="sprint: 1")
    ap.add_argument("--output", default="docs/burndown.html")
    args = ap.parse_args()

    sprint_start = date_parser.parse(args.sprint_start).replace(tzinfo=timezone.utc)
    sprint_end = date_parser.parse(args.sprint_end).replace(tzinfo=timezone.utc)

    print(f"Obteniendo issues del repositorio {args.repo}...")
    issues = fetch_issues(args.token, args.repo, args.label)
    print(f"  → {len(issues)} issues encontrados con label '{args.label}'")

    labels, ideal, real = build_burndown_data(
        issues, sprint_start, sprint_end, args.total_points
    )

    open_count = sum(1 for i in issues if i.get("state") == "open")
    closed_count = sum(1 for i in issues if i.get("state") == "closed")

    html = generate_html(
        labels, ideal, real,
        args.sprint_name, args.total_points,
        closed_count, open_count
    )

    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Burndown chart generado en: {args.output}")


if __name__ == "__main__":
    main()
