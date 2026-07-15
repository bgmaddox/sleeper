entry:        webapp/app.py
run:          lsof -ti :8050 | xargs kill -9 2>/dev/null; sleep 1; cd webapp && source ../.venv/bin/activate && python app.py
core:         sleeper_core.py, data_loader.py  (project root — imported by webapp/ via sys.path)
web:          webapp/app.py (2300+ lines — see SECTION MAP in its docstring for line numbers), webapp/assets/style.css, webapp/assets/d3charts.js
data:         Data/  — NFL player CSVs; .cache/  — pickled season data
config:       config/*.json  — league IDs, roster slots, side bets (loaded by sleeper_core at import)
notebook:     Sleeper_v2.ipynb  (authoritative chart logic reference)
media:        Photos&Videos/  — league logos and draft media
archive:      archive/  (superseded files — old dashboards, planning docs, scratch files)
venv:         .venv/  (Python 3.11)
skip:         __pycache__/, .cache/, .venv/, .git/, archive/, Photos&Videos/
