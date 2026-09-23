entry:        webapp/app.py
run:          lsof -ti :8050 | xargs kill -9 2>/dev/null; sleep 1; cd webapp && source ../.venv/bin/activate && python app.py
core:         sleeper_core.py, data_loader.py, side_bet_resolver.py  (project root — imported by webapp/ via sys.path)
              side_bet_resolver.py — derives weekly side bet winners from final stats;
              hand-entered winners in config/side_bet_seasons.json always take priority
web:          webapp/app.py (3400+ lines — grep the "# ── <name>" section markers listed in its docstring SECTION MAP), webapp/assets/style.css, webapp/assets/d3charts.js, webapp/assets/chartdownload.js (per-card PNG export)
data:         Data/  — NFL player CSVs; .cache/  — pickled season data
config:       config/*.json  — league IDs, roster slots, side bets, manager-name aliases,
              season date overrides (loaded by sleeper_core at import)
notebook:     Sleeper_v3.ipynb  (thin wrapper over sleeper_core — the .py is authoritative; old v2 in archive/)
media:        Photos&Videos/  — league logos and draft media
archive:      archive/  (superseded files — old dashboards, planning docs, scratch files)
venv:         .venv/  (Python 3.12.7)
skip:         __pycache__/, .cache/, .venv/, .git/, archive/, Photos&Videos/
