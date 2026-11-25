"""Quick look at the schematic layout: writes runs/layout_L<n>.png with matplotlib-free plotting
via plotly + kaleido if available. Usage: .venv\Scripts\python tools\preview_layout.py L3"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import mapview  # noqa: E402

for f in (sys.argv[1:] or ["L0"]):
    fig = mapview.floor_figure(f)
    out = ROOT / "runs" / ("layout_%s.png" % f)
    fig.write_image(str(out), width=1500, height=1100)
    print(out)
