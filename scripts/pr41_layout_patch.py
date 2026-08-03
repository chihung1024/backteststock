from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "public/index.html"

text = INDEX.read_text(encoding="utf-8")
style_anchor = '  <link rel="stylesheet" href="/styles.css?v=20260803.5">\n'
style_insert = style_anchor + '  <link rel="stylesheet" href="/backtest-workspace.css?v=20260803.1">\n'
script_anchor = '  <script type="module" src="/scan-composite-score.js?v=20260803.5"></script>\n'
script_insert = script_anchor + '  <script type="module" src="/backtest-workspace.js?v=20260803.1"></script>\n'

if '/backtest-workspace.css?' not in text:
    if style_anchor not in text:
        raise SystemExit("styles.css anchor not found")
    text = text.replace(style_anchor, style_insert, 1)

if '/backtest-workspace.js?' not in text:
    if script_anchor not in text:
        raise SystemExit("scan-composite-score.js anchor not found")
    text = text.replace(script_anchor, script_insert, 1)

INDEX.write_text(text, encoding="utf-8")
