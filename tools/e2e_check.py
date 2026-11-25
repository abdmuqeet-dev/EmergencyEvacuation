r"""Real-browser check of the app. Needs Chrome, `pip install playwright`, and the app running:

    .venv\Scripts\streamlit run src\app.py --server.port 8765        (in another terminal)
    .venv\Scripts\python tools\e2e_check.py [port]

Walks through the demo: start the Lower-floor scenario, autoplay, replay on the timeline, jump floors by
clicking the building overview, click a corridor on the map, block it, see the re-route explained, run to
the end, and switch to presenter mode. Screenshots go to runs/e2e/.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import mapview  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PORT = sys.argv[1] if len(sys.argv) > 1 else "8765"
OUT = ROOT / "runs" / "e2e"
OUT.mkdir(parents=True, exist_ok=True)
_, LAY = mapview._lay()

JS_CLICK = """([which, x, y]) => {const gd = document.querySelectorAll('.js-plotly-plot')[which];
    const r = gd.getBoundingClientRect(); const xa = gd._fullLayout.xaxis, ya = gd._fullLayout.yaxis;
    return [r.left + xa._offset + xa.l2p(x), r.top + ya._offset + ya.l2p(y)];}"""


def click_plot(pg, which, x, y):
    """Click a Plotly chart at data coordinates (which = 0 for the floor map, 1 for the overview: DOM order, left column first)."""
    box = pg.evaluate(JS_CLICK, [which, x, y])
    pg.mouse.click(box[0], box[1])


def main():
    problems = []

    def check(ok, what):
        if not ok:
            problems.append(what)

    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome", headless=True)
        pg = br.new_page(viewport={"width": 1800, "height": 1250})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:%s" % PORT, wait_until="networkidle")
        pg.wait_for_timeout(2000)
        pg.locator("[data-testid=stSidebar] [data-testid=stSelectbox]").first.click()
        pg.get_by_role("option", name="s6_midrun_block_lower").click()
        pg.wait_for_timeout(1500)
        pg.get_by_role("button", name="Start").click()
        pg.wait_for_selector(".evac-banner", timeout=90000)
        pg.wait_for_timeout(2500)
        pg.screenshot(path=str(OUT / "1_started.png"))

        # autoplay
        pg.get_by_role("button", name="Play").click()
        pg.wait_for_timeout(4500)
        pg.get_by_role("button", name="Pause").click()
        pg.wait_for_timeout(1500)
        sub = pg.locator(".evac-sub").inner_text()
        check("Step" in sub and "Step 0" not in sub and "Start" not in sub, "Play did not advance the simulation (%r)" % sub)
        pg.screenshot(path=str(OUT / "2_played.png"))

        # replay with the timeline: arrow keys on the slider thumb
        pg.locator("[data-testid=stSlider]").last.locator("input").focus()
        for _ in range(2):
            pg.keyboard.press("ArrowLeft")
            pg.wait_for_timeout(700)
        pg.wait_for_timeout(1500)
        check(pg.locator(".evac-replay").count() == 1, "dragging the timeline back did not show the replay strip")
        pg.screenshot(path=str(OUT / "3_replay.png"))
        pg.get_by_role("button", name="Back to live").click()
        pg.wait_for_timeout(1500)
        check(pg.locator(".evac-replay").count() == 0, "Back to live did not leave replay")

        # start over, so the group is back on the way to the north exit (autoplay has walked it past it)
        pg.get_by_role("button", name="Restart").click()
        pg.wait_for_function("document.querySelector('.evac-sub') && document.querySelector('.evac-sub').innerText.startsWith('Start')",
                             timeout=60000)
        pg.wait_for_timeout(1500)
        for _ in range(2):
            pg.get_by_role("button", name="Next step").click()
            pg.wait_for_timeout(1500)

        # overview: click the 1st-floor band, then the Lower floor band again
        click_plot(pg, 1, mapview.OVERVIEW_PICK_X, 1.5)
        pg.wait_for_timeout(3000)
        check("1st floor (north is up)" in pg.inner_text("body"), "clicking a level in the overview did not open it")
        pg.screenshot(path=str(OUT / "4_overview_click.png"))
        click_plot(pg, 1, mapview.OVERVIEW_PICK_X, 0.5)
        pg.wait_for_timeout(3000)
        check("Lower floor (north is up)" in pg.inner_text("body"), "clicking the Lower level in the overview did not open it")

        # block a corridor on the group's route, then see the re-route explained
        x, y = LAY.pos["L0_c_c_n"]
        click_plot(pg, 0, x, y)
        pg.wait_for_timeout(3000)
        chip = pg.locator("[data-testid=stMultiSelect]").nth(1).inner_text()
        check("north exit" in chip, "clicking the map did not select the corridor (selection box shows %r)" % chip)
        pg.get_by_role("button", name="Block", exact=True).click()
        pg.wait_for_timeout(9000)
        card = pg.locator(".evac-card").inner_text()
        check("new plan verified" in card and "re-routed" in card, "the re-route was not explained (%r)" % card)
        pg.screenshot(path=str(OUT / "5_replanned.png"))
        pg.get_by_role("button", name="Run to end").click()
        pg.wait_for_timeout(4000)
        check("Everyone is out" in pg.locator(".evac-banner").inner_text(), "the run did not finish with everyone out")
        pg.screenshot(path=str(OUT / "6_done.png"))

        # presenter mode
        pg.get_by_text("Presenter mode").click()
        pg.wait_for_timeout(3000)
        check(not pg.locator("[data-testid=stSidebar]").is_visible(), "presenter mode did not hide the sidebar")
        pg.screenshot(path=str(OUT / "7_presenter.png"))

        problems += ["browser error: " + e for e in errs]
        br.close()
    print("PROBLEMS:\n  " + "\n  ".join(problems) if problems else "browser check passed (screenshots in runs/e2e/)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
