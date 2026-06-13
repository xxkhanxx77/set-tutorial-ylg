"""Render an executed tutorial notebook into a designed, responsive, dual-mode HTML page.

Usage:  uv run python render_tutorial_html.py [notebook.ipynb]
        (defaults to usdtthb_spread_tutorial.ipynb)
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import mistune
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

NB = sys.argv[1] if len(sys.argv) > 1 else "usdtthb_spread_tutorial.ipynb"
OUT = str(Path(NB).with_suffix(".html"))

with open(NB) as f:
    nb = json.load(f)

md_render = mistune.create_markdown(plugins=["table", "strikethrough", "url"], escape=False)
py_lexer = PythonLexer()
light_fmt = HtmlFormatter(style="friendly", cssclass="hl")
dark_fmt = HtmlFormatter(style="native", cssclass="hl")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def src(cell):
    s = cell["source"]
    return s if isinstance(s, str) else "".join(s)


title = Path(NB).stem.replace("_", " ").title()
toc, body_parts = [], []

for cell in nb["cells"]:
    if cell["cell_type"] == "markdown":
        text = src(cell)
        m = re.match(r"^# (.+)$", text, re.M)
        if m and not toc and "<h1" not in "".join(body_parts):
            title = m.group(1).strip()
            text = re.sub(r"^# .+\n?", "", text, count=1)

        def h2_repl(match):
            h = match.group(1).strip()
            toc.append(h)
            return f'<h2 id="{slug(h)}">{h}</h2>'

        html = md_render(text)
        html = re.sub(r"<h2>(.+?)</h2>", h2_repl, html)
        body_parts.append(f'<section class="prose">{html}</section>')
    elif cell["cell_type"] == "code":
        code_html = highlight(src(cell), py_lexer, light_fmt)
        body_parts.append(
            f'<figure class="code"><figcaption>python</figcaption>{code_html}</figure>')
        for out in cell.get("outputs", []):
            ot = out.get("output_type")
            if ot == "stream":
                txt = out["text"]
                txt = txt if isinstance(txt, str) else "".join(txt)
                body_parts.append(
                    f'<figure class="result"><figcaption>output</figcaption>'
                    f'<pre>{txt.replace("&", "&amp;").replace("<", "&lt;")}</pre></figure>')
            elif ot in ("execute_result", "display_data"):
                data = out.get("data", {})
                if "image/png" in data:
                    png = data["image/png"]
                    png = png if isinstance(png, str) else "".join(png)
                    body_parts.append(
                        f'<figure class="chart"><img alt="chart" loading="lazy" '
                        f'src="data:image/png;base64,{png.strip()}"></figure>')
                elif "text/html" in data:
                    h = data["text/html"]
                    h = h if isinstance(h, str) else "".join(h)
                    h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
                    body_parts.append(
                        f'<figure class="result table-wrap"><figcaption>output</figcaption>{h}</figure>')
                elif "text/plain" in data:
                    t = data["text/plain"]
                    t = t if isinstance(t, str) else "".join(t)
                    body_parts.append(
                        f'<figure class="result"><figcaption>output</figcaption>'
                        f'<pre>{t.replace("&", "&amp;").replace("<", "&lt;")}</pre></figure>')

toc_html = "".join(f'<a href="#{slug(h)}">{h.replace("Step ", "")}</a>' for h in toc)
light_css = light_fmt.get_style_defs(".hl")
dark_css = dark_fmt.get_style_defs(".hl")

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg: #faf7f2; --bg2: #f1ece3; --ink: #211d18; --muted: #6f675c;
  --accent: #0d6b58; --accent2: #b97f10; --line: #e3dccf;
  --card: #ffffff; --code-bg: #f6f2ea; --danger: #a33a2a;
  --radius: 14px;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #15130f; --bg2: #1c1914; --ink: #ece7dd; --muted: #9b9385;
    --accent: #56cfae; --accent2: #e0a83c; --line: #2e2a22;
    --card: #1e1b15; --code-bg: #211e17; --danger: #e07a5f;
  }}
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  margin: 0; background: var(--bg); color: var(--ink);
  font: 17px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
}}
header.hero {{
  background: linear-gradient(160deg, var(--bg2), var(--bg) 70%);
  border-bottom: 1px solid var(--line);
  padding: clamp(2.5rem, 7vw, 5rem) 1.25rem clamp(2rem, 5vw, 3.5rem);
}}
.hero-inner, main, footer.colophon div {{ max-width: 880px; margin: 0 auto; }}
.overline {{
  font-size: .72rem; letter-spacing: .22em; text-transform: uppercase;
  color: var(--accent); font-weight: 700; margin-bottom: 1.1rem;
}}
h1 {{
  font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  font-size: clamp(1.9rem, 5.2vw, 3.1rem); line-height: 1.12;
  letter-spacing: -.015em; margin: 0 0 1.2rem; font-weight: 600;
}}
.chips {{ display: flex; flex-wrap: wrap; gap: .5rem; }}
.chip {{
  font-size: .76rem; font-weight: 600; padding: .32rem .75rem;
  border: 1px solid var(--line); border-radius: 999px; color: var(--muted);
  background: var(--card);
}}
.chip.live {{ color: var(--accent); border-color: var(--accent); }}
.chip.warn {{ color: var(--accent2); border-color: var(--accent2); }}
nav.toc {{
  position: sticky; top: 0; z-index: 9; background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(10px); border-bottom: 1px solid var(--line);
  overflow-x: auto; white-space: nowrap; padding: .55rem 1.25rem;
  display: flex; gap: .35rem; scrollbar-width: none;
}}
nav.toc::-webkit-scrollbar {{ display: none; }}
nav.toc a {{
  font-size: .78rem; font-weight: 600; color: var(--muted); text-decoration: none;
  padding: .3rem .7rem; border-radius: 999px;
}}
nav.toc a:hover {{ color: var(--accent); background: var(--bg2); }}
main {{ padding: clamp(1.5rem, 4vw, 3rem) 1.25rem 4rem; }}
.prose {{ max-width: 720px; }}
.prose h2 {{
  font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  font-size: clamp(1.35rem, 3vw, 1.8rem); line-height: 1.2; font-weight: 600;
  margin: 3.2rem 0 1rem; padding-top: 1.2rem; position: relative;
}}
.prose h2::before {{
  content: ""; position: absolute; top: 0; left: 0; width: 52px; height: 3px;
  background: var(--accent); border-radius: 2px;
}}
.prose h3 {{ font-size: 1.12rem; margin: 2.2rem 0 .6rem; }}
.prose p {{ margin: .85rem 0; }}
.prose a {{ color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 3px; }}
.prose ul, .prose ol {{ padding-left: 1.4rem; }}
.prose li {{ margin: .35rem 0; }}
.prose blockquote {{
  margin: 1.4rem 0; padding: .9rem 1.2rem; border-left: 4px solid var(--accent2);
  background: var(--bg2); border-radius: 0 var(--radius) var(--radius) 0;
  color: var(--ink); font-size: .95rem;
}}
.prose blockquote p {{ margin: .4rem 0; }}
.prose code, .result pre, figure.code pre {{
  font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;
}}
.prose code {{
  background: var(--code-bg); border: 1px solid var(--line);
  padding: .12em .4em; border-radius: 6px; font-size: .84em;
}}
.prose pre {{
  background: var(--code-bg); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 1rem 1.2rem; overflow-x: auto; font-size: .84rem; line-height: 1.55;
}}
.prose pre code {{ background: none; border: 0; padding: 0; }}
table {{
  border-collapse: collapse; width: 100%; margin: 1.2rem 0; font-size: .86rem;
}}
th, td {{ text-align: left; padding: .55rem .8rem; border-bottom: 1px solid var(--line); }}
th {{
  font-size: .72rem; text-transform: uppercase; letter-spacing: .08em;
  color: var(--muted); border-bottom: 2px solid var(--line);
}}
tbody tr:hover {{ background: var(--bg2); }}
figure {{ margin: 1.6rem 0; }}
figure.code, figure.result {{
  background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
  overflow: hidden; box-shadow: 0 1px 2px rgb(0 0 0 / .04);
}}
figure.code figcaption, figure.result figcaption {{
  font-size: .68rem; font-weight: 700; letter-spacing: .18em; text-transform: uppercase;
  color: var(--muted); padding: .5rem 1.1rem; border-bottom: 1px solid var(--line);
  background: var(--bg2);
}}
figure.result figcaption {{ color: var(--accent); }}
figure.code .hl pre, figure.result pre {{
  margin: 0; padding: 1rem 1.2rem; overflow-x: auto;
  font-size: .8rem; line-height: 1.6; background: none; border: 0;
}}
figure.code .hl {{ background: var(--code-bg); }}
figure.result pre {{ color: var(--ink); }}
figure.result.table-wrap {{ overflow-x: auto; }}
figure.result.table-wrap table {{ margin: 0; min-width: 480px; }}
figure.result.table-wrap > div {{ padding: .4rem 1.1rem 1rem; overflow-x: auto; }}
figure.chart {{
  background: #fff; border: 1px solid var(--line); border-radius: var(--radius);
  padding: .8rem; box-shadow: 0 1px 3px rgb(0 0 0 / .05);
}}
figure.chart img {{ display: block; width: 100%; height: auto; border-radius: 6px; }}
hr {{ border: 0; border-top: 1px solid var(--line); margin: 3rem 0; }}
footer.colophon {{
  border-top: 1px solid var(--line); background: var(--bg2);
  padding: 2rem 1.25rem; font-size: .82rem; color: var(--muted);
}}
footer.colophon a {{ color: var(--accent); }}
{light_css}
@media (prefers-color-scheme: dark) {{
{dark_css}
figure.code .hl {{ background: var(--code-bg); }}
}}
@media (max-width: 640px) {{
  body {{ font-size: 16px; }}
  th, td {{ padding: .45rem .55rem; }}
}}
</style>
</head>
<body>
<header class="hero">
  <div class="hero-inner">
    <div class="overline">set-bot-lab · tutorial series</div>
    <h1>{title}</h1>
    <div class="chips">
      <span class="chip live">real bid/ask data</span>
      <span class="chip">runnable notebook</span>
      <span class="chip warn">no orders placed</span>
      <span class="chip">generated {date.today():%d %b %Y}</span>
    </div>
  </div>
</header>
<nav class="toc">{toc_html}</nav>
<main>
{"".join(body_parts)}
</main>
<footer class="colophon">
  <div>Companion files: <code>{Path(NB).name}</code> · <code>{Path(NB).stem}.md</code>
  · full study in <code>simple_spread_strategy.ipynb</code>. Educational only — not investment advice.</div>
</footer>
</body>
</html>"""

with open(OUT, "w") as f:
    f.write(page)
print(f"Wrote {OUT} ({len(page) / 1024:.0f} KB), {len(toc)} sections")
