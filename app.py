"""
Smart Stop — Interactive Web Demo
===================================
Run:  streamlit run app.py
"""

import os
import sys
import tempfile
import streamlit as st

# ── path setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from config import OUTPUT_DIR

# ── page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Smart Stop — Intersection Demo",
    page_icon="🛑",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── constants ────────────────────────────────────────────────────────────────
ROADS = ["Main E", "Main W", "Green N", "Green S"]
SIGNALS = {"None": None, "Right (R)": "R", "Left (L)": "L", "Straight": "NS/S"}
SIGNAL_COLORS = {"R": "#9B59B6", "L": "#27AE60", "NS/S": "#E67E22"}

PRESETS = {
    "Demo 1 — Non-conflicting Right Turns": [
        ("Main E", "R", 1),
        ("Green N", "R", 2),
    ],
    "Demo 2 — Mixed Signals": [
        ("Main E", "R", 1),
        ("Green N", "L", 2),
        ("Main W", "NS/S", 3),
        ("Green S", "R", 4),
    ],
    "Demo 3 — Backward Priority": [
        ("Main W", "NS/S", 1),
        ("Green S", "R", 2),
    ],
    "Demo 4 — Rush Hour (6 vehicles)": [
        ("Main E", "R", 1),
        ("Green N", "L", 2),
        ("Main W", "NS/S", 3),
        ("Green S", "R", 4),
        ("Main E", "L", 5),
        ("Green N", "NS/S", 6),
    ],
}

ALG_ORDER = ["Smart Stop", "Traditional", "Roundabout", "Smart Safe"]
ALG_COLORS = {
    "Smart Stop":  "#2ECC71",
    "Roundabout":  "#3498DB",
    "Smart Safe":  "#F39C12",
    "Traditional": "#E74C3C",
}


# ── helpers ──────────────────────────────────────────────────────────────────
def build_vehicles(rows):
    """Convert sidebar rows → PathBasedVehicle list, ordered by arrival order."""
    from path_based_smart_stop import PathBasedVehicle, FourWayGeometry
    geometry = FourWayGeometry()
    vehicles = []
    for road, signal, order in rows:
        vehicles.append(PathBasedVehicle(road, signal, order, geometry))
    return vehicles


@st.cache_data(show_spinner=False)
def run_and_animate(vehicle_tuples: tuple) -> dict:
    """
    Run all 4 algorithms and generate a GIF.
    Cached by vehicle_tuples so identical scenarios don't re-run.
    Returns dict with gif_path and metrics per algorithm.
    """
    from path_based_smart_stop import PathBasedVehicle, FourWayGeometry, AlgorithmComparison
    from enhanced_visualization import EnhancedIntersectionAnimator

    geometry = FourWayGeometry()
    vehicles = [PathBasedVehicle(road, sig, order, geometry)
                for road, sig, order in vehicle_tuples]

    comparison = AlgorithmComparison(vehicles, "4way")
    results = comparison.run_comparison()

    # Save GIF to a temp file so multiple concurrent runs don't collide
    tmp = tempfile.NamedTemporaryFile(suffix=".gif", delete=False, dir=OUTPUT_DIR)
    tmp.close()
    animator = EnhancedIntersectionAnimator(results, "4way")
    animator.animate(save_path=tmp.name, show=False)

    metrics = {}
    for alg_name, data in results.items():
        m = data.get("metrics", {})
        metrics[alg_name] = {
            "total_time": m.get("total_time", 0.0),
            "avg_wait":   m.get("avg_wait_time", 0.0),
        }

    return {"gif_path": tmp.name, "metrics": metrics}


def fmt_delta(base_time, compare_time):
    """Return coloured markdown showing % less time vs baseline."""
    if base_time <= 0:
        return "—"
    pct = (base_time - compare_time) / base_time * 100
    if pct > 1:
        return f"<span style='color:#2ECC71'>**{pct:.0f}% less time**</span>"
    elif pct < -1:
        return f"<span style='color:#E74C3C'>**{abs(pct):.0f}% more time**</span>"
    return "≈ same"


# ── sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🛑 Smart Stop")
    st.caption("Intersection algorithm demo")

    st.divider()

    # Preset loader
    preset_choice = st.selectbox(
        "Load a preset scenario",
        ["— custom —"] + list(PRESETS.keys()),
    )

    st.divider()
    st.subheader("Scenario builder")
    st.caption("Set turn signal for each approach. Arrival order = top to bottom.")

    # Seed UI from preset or defaults
    seed = PRESETS.get(preset_choice, [])
    seed_map = {r: (sig, i + 1) for i, (r, sig, _) in enumerate(seed)}

    vehicle_rows = []
    for idx, road in enumerate(ROADS):
        col1, col2 = st.columns([3, 1])
        default_signal = seed_map[road][0] if road in seed_map else "None"
        default_order  = seed_map[road][1] if road in seed_map else idx + 1

        # Map signal back to display label
        sig_label_map = {v: k for k, v in SIGNALS.items()}
        sig_label_map[None] = "None"
        default_label = sig_label_map.get(default_signal, "None")

        with col1:
            sig_display = st.selectbox(
                road,
                list(SIGNALS.keys()),
                index=list(SIGNALS.keys()).index(default_label),
                key=f"sig_{road}_{preset_choice}",
            )
        with col2:
            order = st.number_input(
                "Order",
                min_value=1, max_value=10,
                value=default_order,
                key=f"ord_{road}_{preset_choice}",
                label_visibility="collapsed",
            )

        sig_val = SIGNALS[sig_display]
        if sig_val is not None:
            vehicle_rows.append((road, sig_val, int(order)))

    if not vehicle_rows:
        st.warning("Add at least one vehicle to run.")

    st.divider()
    run_btn = st.button(
        "▶ Run simulation",
        type="primary",
        disabled=len(vehicle_rows) == 0,
        use_container_width=True,
    )

# ── main panel ───────────────────────────────────────────────────────────────
st.title("Smart Stop — Algorithm Comparison")
st.caption(
    "4-way intersection coordination · Traditional vs Roundabout vs Smart Stop vs Smart Safe"
)

# Show pending vehicle summary
if vehicle_rows:
    sig_names = {"R": "Right ➜", "L": "Left ↰", "NS/S": "Straight ↑"}
    cols = st.columns(len(vehicle_rows))
    for col, (road, sig, order) in zip(cols, sorted(vehicle_rows, key=lambda x: x[2])):
        col.metric(
            label=f"#{order} · {road}",
            value=sig_names.get(sig, sig),
            delta=None,
        )
    st.divider()

# ── run / display ─────────────────────────────────────────────────────────────
if run_btn and vehicle_rows:
    # Sort by arrival order before passing to cache key (order matters)
    key = tuple(sorted(vehicle_rows, key=lambda x: x[2]))

    with st.spinner("Running simulation and rendering GIF… (typically 30–60 seconds)"):
        try:
            output = run_and_animate(key)
        except Exception as e:
            st.error(f"Simulation failed: {e}")
            st.stop()

    gif_path = output["gif_path"]
    metrics  = output["metrics"]

    # ── GIF display ──
    st.subheader("Animation")
    st.caption(
        "Top-left: Traditional  ·  Top-right: Roundabout  ·  "
        "Bottom-left: Smart Stop  ·  Bottom-right: Smart Safe"
    )
    with open(gif_path, "rb") as f:
        gif_bytes = f.read()
    st.image(gif_bytes, use_container_width=True)

    st.divider()

    # ── metrics table ──
    st.subheader("Results")
    trad_time = metrics.get("Traditional", {}).get("total_time", 0)

    result_cols = st.columns(len(ALG_ORDER))
    for col, alg in zip(result_cols, ALG_ORDER):
        m = metrics.get(alg, {})
        t = m.get("total_time", 0.0)
        color = ALG_COLORS[alg]
        delta_str = fmt_delta(trad_time, t) if alg != "Traditional" else "baseline"
        col.markdown(
            f"""
            <div style="border-left: 4px solid {color}; padding: 12px 16px;
                        background: #1a1a2e; border-radius: 4px;">
              <div style="font-size:1.1em; font-weight:600; color:{color}">{alg}</div>
              <div style="font-size:2em; font-weight:700; color:#fff">{t:.1f}s</div>
              <div style="font-size:0.85em; color:#aaa">vs Traditional: {delta_str}</div>
              <div style="font-size:0.85em; color:#888">avg wait: {m.get('avg_wait', 0):.1f}s</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── insight line ──
    ss_time = metrics.get("Smart Stop", {}).get("total_time", 1)
    if trad_time > 0 and ss_time < trad_time:
        pct = (trad_time - ss_time) / trad_time * 100
        st.success(
            f"Smart Stop cleared the intersection in **{ss_time:.1f}s** — "
            f"**{pct:.0f}% less time** than Traditional ({trad_time:.1f}s)."
        )

elif not run_btn:
    # Empty state
    st.info(
        "Configure a scenario in the sidebar and click **▶ Run simulation**.\n\n"
        "Try a preset to reproduce the presentation demos instantly."
    )
