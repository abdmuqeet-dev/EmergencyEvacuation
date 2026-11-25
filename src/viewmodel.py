"""Small pure helpers that turn simulation data into the numbers and sentences the UI shows.

Kept out of app.py so they can be tested without running Streamlit.
"""
from html import escape

CLASS_OF = {"done": "ok", "stuck": "bad", "live": "live"}


def stats(frame, replans=0, valid=True):
    """Counts for the banner from one simulation frame (see Simulation._snap)."""
    st = [g["status"] for g in frame["groups"].values()]
    n = len(st)
    out, walking = st.count("out"), st.count("walking")
    sheltered, stuck = st.count("sheltered"), st.count("stuck")
    if stuck:
        state = "stuck" if not walking else "live"
    elif walking == 0:
        state = "done"
    else:
        state = "live"
    return {"total": n, "out": out, "walking": walking, "sheltered": sheltered, "stuck": stuck,
            "replans": replans, "valid": bool(valid), "state": state, "step": frame["step"], "label": frame["label"]}


def change_sentences(event, group_names=None):
    """One sentence per group whose plan changed in this event."""
    out = []
    for gid, ch in event.get("changes", {}).items():
        who = (group_names or {}).get(gid, gid)
        if ch["was"] != "walking" and ch["now"] == "walking":
            out.append("%s can leave its shelter now: %d actions to the exit." % (who, ch["after"]))
        elif ch["now"] == "sheltered":
            out.append("%s has no safe way down any more and will shelter and call for help." % who)
        elif ch["now"] == "stuck":
            out.append("%s has no way out." % who)
        else:
            d = ch["after"] - ch["before"]
            word = "%d actions longer" % d if d > 0 else ("%d actions shorter" % -d if d < 0 else "the same length")
            out.append("%s is re-routed: %d -> %d actions left (%s)." % (who, ch["before"], ch["after"], word))
    return out


def banner_html(s, scenario_text="", replay=False, replay_note=""):
    """The big status strip at the top of the page."""
    cls = CLASS_OF[s["state"]]
    chips = []
    if s["walking"]:
        chips.append("%d evacuating" % s["walking"])
    if s["sheltered"]:
        chips.append("%d sheltering" % s["sheltered"])
    if s["stuck"]:
        chips.append("%d STUCK" % s["stuck"])
    chips.append("%d re-plan%s" % (s["replans"], "" if s["replans"] == 1 else "s"))
    chips.append("plans verified by VAL" if s["valid"] else "A PLAN WAS REJECTED")
    headline = "%d of %d out of the building" % (s["out"], s["total"])
    if s["state"] == "done" and s["out"] == s["total"]:
        headline = "Everyone is out: %d of %d" % (s["out"], s["total"])
    elif s["state"] == "done":
        headline = "Everyone is accounted for"
    html = ["<div class='evac-banner %s'>" % cls,
            "<div><div class='evac-big'>%s</div><div class='evac-sub'>%s &middot; %s</div></div>"
            % (escape(headline), escape(s["label"]), escape(scenario_text)),
            "<div class='evac-chips'>%s</div></div>" % "".join("<span class='evac-chip'>%s</span>" % escape(c) for c in chips)]
    if replay:
        html.append("<div class='evac-replay'>Replay: %s. This is a past moment; press <b>Back to live</b> to continue. %s</div>"
                    % (escape(s["label"]), escape(replay_note)))
    return "".join(html)


CSS = """
<style>
.block-container {padding-top: 3.2rem; max-width: 100%;}
.evac-banner {display:flex; justify-content:space-between; align-items:center; gap:24px; flex-wrap:wrap;
  border-radius:14px; padding:14px 22px; color:#fff; margin-bottom:10px;
  background:linear-gradient(90deg,#00274c 0%,#1d4f86 100%); box-shadow:0 2px 6px rgba(0,0,0,.18);}
.evac-banner.ok {background:linear-gradient(90deg,#14532d 0%,#1f8a4c 100%);}
.evac-banner.bad {background:linear-gradient(90deg,#7f1d1d 0%,#c0392b 100%);}
.evac-big {font-size:2.0rem; font-weight:800; line-height:1.15;}
.evac-sub {opacity:.85; font-size:.95rem; margin-top:2px;}
.evac-chips {display:flex; gap:8px; flex-wrap:wrap;}
.evac-chip {background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.35); border-radius:999px;
  padding:5px 13px; font-weight:600; font-size:.95rem;}
.evac-replay {width:100%; background:#fff3cd; color:#664d03; border-radius:8px; padding:6px 12px; font-size:.95rem;}
.evac-card {border-left:6px solid #ff7900; background:#fff7ec; border-radius:8px; padding:10px 14px; margin:6px 0 10px;}
.evac-card b {color:#a14a00;}
h1, h2, h3 {letter-spacing:-0.01em;}
</style>
"""

PRESENTER_CSS = """
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none;}
html {font-size: 18px;}
.evac-big {font-size:2.6rem;}
</style>
"""
