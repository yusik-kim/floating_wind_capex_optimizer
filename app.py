import math

import pandas as pd
import streamlit as st

from engine import (
    TURBINE_LIBRARY,
    design_inputs_from_turbine,
    evaluate_semisub,
    optimize_capex,
    result_as_dict,
    turbine_from_capacity,
)


st.set_page_config(page_title="Floating Wind CAPEX Optimizer v0.4", layout="wide")


def money_musd(value: float) -> str:
    return f"${value:,.1f}M"


def compact_number(value: float, unit: str = "") -> str:
    if abs(value) >= 1000:
        text = f"{value:,.0f}"
    elif abs(value) >= 100:
        text = f"{value:,.1f}"
    else:
        text = f"{value:,.2f}"
    return f"{text} {unit}".strip()


def platform_top_svg(result) -> str:
    width, height = 520, 360
    cx, cy = width / 2, height / 2
    scale = min(2.25, 165.0 / max(result.column_spacing_m, 1.0))
    radius = result.column_spacing_m / math.sqrt(3.0) * scale
    col_r = max(12.0, result.column_diameter_m * scale / 2.0)
    points = [
        (cx + radius, cy),
        (cx - 0.5 * radius, cy + math.sqrt(3.0) * radius / 2.0),
        (cx - 0.5 * radius, cy - math.sqrt(3.0) * radius / 2.0),
    ]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    lines = "".join(
        f'<line x1="{points[i][0]:.1f}" y1="{points[i][1]:.1f}" '
        f'x2="{points[(i + 1) % 3][0]:.1f}" y2="{points[(i + 1) % 3][1]:.1f}" />'
        for i in range(3)
    )
    cols = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{col_r:.1f}" />'
        for x, y in points
    )
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="Top view platform layout">
      <style>
        .frame {{ fill:#f8fafc; stroke:#cbd5e1; }}
        .pontoon {{ stroke:#64748b; stroke-width:18; stroke-linecap:round; fill:none; }}
        .deck {{ fill:#dbeafe; stroke:#2563eb; stroke-width:2; opacity:0.42; }}
        .column {{ fill:#0f766e; stroke:#0f172a; stroke-width:2; }}
        .label {{ font: 15px system-ui, sans-serif; fill:#0f172a; }}
        .small {{ font: 13px system-ui, sans-serif; fill:#475569; }}
      </style>
      <rect class="frame" x="8" y="8" width="{width-16}" height="{height-16}" rx="8" />
      <polygon class="deck" points="{poly}" />
      <g class="pontoon">{lines}</g>
      <g class="column">{cols}</g>
      <text class="label" x="24" y="34">Top layout</text>
      <text class="small" x="24" y="314">Column dia: {result.column_diameter_m:.1f} m</text>
      <text class="small" x="24" y="336">Spacing: {result.column_spacing_m:.1f} m</text>
    </svg>
    """


def platform_side_svg(result, max_column_diameter_m: float) -> str:
    width, height = 520, 360
    water_y = 132
    keel_y = 300
    draft_px = 120.0
    col_height_px = max(155.0, draft_px * result.column_height_m / max(result.draft_m, 1.0))
    top_y = keel_y - col_height_px
    col_w = max(34.0, min(88.0, result.column_diameter_m * 4.7))
    spacing_px = min(310.0, max(170.0, result.column_spacing_m * 3.5))
    x1, x2 = width / 2 - spacing_px / 2, width / 2 + spacing_px / 2
    ratio = min(1.0, result.column_diameter_m / max(max_column_diameter_m, 1e-6))
    fill = "#dc2626" if ratio > 1.0 else "#0f766e"
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="Side view platform layout">
      <style>
        .frame {{ fill:#f8fafc; stroke:#cbd5e1; }}
        .water {{ fill:#bfdbfe; opacity:0.62; }}
        .waterline {{ stroke:#2563eb; stroke-width:2; stroke-dasharray:7 7; }}
        .column {{ fill:{fill}; stroke:#0f172a; stroke-width:2; }}
        .pontoon {{ fill:#334155; opacity:0.92; }}
        .label {{ font: 15px system-ui, sans-serif; fill:#0f172a; }}
        .small {{ font: 13px system-ui, sans-serif; fill:#475569; }}
      </style>
      <rect class="frame" x="8" y="8" width="{width-16}" height="{height-16}" rx="8" />
      <rect class="water" x="9" y="{water_y}" width="{width-18}" height="{height-water_y-9}" />
      <line class="waterline" x1="18" y1="{water_y}" x2="{width-18}" y2="{water_y}" />
      <rect class="pontoon" x="{x1-col_w/2:.1f}" y="{keel_y-28}" width="{x2-x1+col_w:.1f}" height="28" rx="4" />
      <rect class="column" x="{x1-col_w/2:.1f}" y="{top_y:.1f}" width="{col_w:.1f}" height="{col_height_px:.1f}" rx="5" />
      <rect class="column" x="{x2-col_w/2:.1f}" y="{top_y:.1f}" width="{col_w:.1f}" height="{col_height_px:.1f}" rx="5" />
      <text class="label" x="24" y="34">Side layout</text>
      <text class="small" x="24" y="314">Draft: {result.draft_m:.1f} m</text>
      <text class="small" x="24" y="336">Column height: {result.column_height_m:.1f} m</text>
    </svg>
    """


st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; max-width: 1180px; }
      [data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.75rem 0.85rem;
      }
      [data-testid="stMetric"] label,
      [data-testid="stMetric"] [data-testid="stMetricLabel"],
      [data-testid="stMetric"] [data-testid="stMetricValue"],
      [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: #0f172a !important;
      }
      [data-testid="stMetric"] [data-testid="stMetricLabel"] p,
      [data-testid="stMetric"] [data-testid="stMetricValue"] div,
      [data-testid="stMetric"] [data-testid="stMetricDelta"] div {
        color: #0f172a !important;
      }
      div[data-testid="stVerticalBlock"] > div:has(svg) {
        overflow-x: auto;
      }
      @media (max-width: 760px) {
        .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
        [data-testid="stMetric"] { padding: 0.6rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Floating Wind CAPEX Optimizer v0.4")
st.caption("A concept-screening optimizer for non-experts: adjust turbine, draft, pitch and offset, then compare against the lowest CAPEX case.")

with st.sidebar:
    st.header("Minimize CAPEX")
    optimize_wtg = st.toggle("Optimize WTG capacity", value=True)
    if optimize_wtg:
        turbine_mw = 15.0
    else:
        turbine_mw = st.slider("WTG capacity [MW]", 8.0, 20.0, 15.0, 1.0)

    optimize_draft = st.toggle("Optimize draft", value=True)
    if optimize_draft:
        target_draft_m = 20.0
    else:
        target_draft_m = st.slider("Draft [m]", 14.0, 28.0, 20.0, 1.0)

    optimize_pitch = st.toggle("Optimize pitch limit", value=True)
    if optimize_pitch:
        allowable_pitch_deg = 8.0
    else:
        allowable_pitch_deg = st.slider("Pitch limit [deg]", 5.0, 10.0, 8.0, 0.5)

    optimize_offset = st.toggle("Optimize offset limit", value=True)
    if optimize_offset:
        allowable_offset_pct_depth = 5.0
    else:
        allowable_offset_pct_depth = st.slider("Offset limit [% water depth]", 3.0, 8.0, 5.0, 0.5)

    st.header("Site")
    water_depth_m = st.number_input("Water depth [m]", 40.0, 1500.0, 200.0, 10.0)
    hs_m = st.number_input("Significant wave height Hs [m]", 1.0, 20.0, 8.0, 0.5)
    tp_s = st.number_input("Peak period Tp [s]", 4.0, 25.0, 12.0, 0.5)
    port_draft_limit_m = st.number_input("Port / tow-out draft limit [m]", 5.0, 80.0, 25.0, 1.0)

    st.header("Constraints")
    max_column_diameter_m = st.number_input("Max column diameter [m]", 6.0, 30.0, 12.0, 0.5)
    gm_min_m = st.number_input("Minimum GM [m]", 0.5, 10.0, 2.0, 0.5)
    restoring_ratio_min = st.number_input("Minimum restoring / heeling ratio", 1.0, 3.0, 1.3, 0.1)
    mooring_line_count = st.number_input("Number of mooring lines", 3, 12, 3, 1)
    mooring_safety_factor = st.number_input("Mooring safety factor", 1.0, 3.0, 1.5, 0.1)
    mooring_cost_multiplier = st.number_input("Mooring cost multiplier", 0.5, 3.0, 1.0, 0.1)

base_inputs = design_inputs_from_turbine(
    turbine_mw=turbine_mw,
    water_depth_m=water_depth_m,
    hs_m=hs_m,
    tp_s=tp_s,
    port_draft_limit_m=port_draft_limit_m,
    gm_min_m=gm_min_m,
    allowable_pitch_deg=allowable_pitch_deg,
    restoring_ratio_min=restoring_ratio_min,
    mooring_line_count=mooring_line_count,
    allowable_offset_pct_depth=allowable_offset_pct_depth,
    mooring_safety_factor=mooring_safety_factor,
    mooring_cost_multiplier=mooring_cost_multiplier,
    max_column_diameter_m=max_column_diameter_m,
    target_draft_m=target_draft_m,
)

optimized_result = optimize_capex(base_inputs, True, True, True, True)
result = optimize_capex(base_inputs, optimize_wtg, optimize_draft, optimize_pitch, optimize_offset)
manual_result = evaluate_semisub(base_inputs)

delta_musd = result.total_capex_musd - optimized_result.total_capex_musd
delta_pct = 100.0 * delta_musd / max(optimized_result.total_capex_musd, 1e-6)
status = "PASS" if result.overall_pass else "CHECK"

c1, c2, c3 = st.columns([1.2, 1, 1])
c1.metric("Selected CAPEX", money_musd(result.total_capex_musd), f"{money_musd(delta_musd)} vs optimum")
c2.metric("Optimized CAPEX", money_musd(optimized_result.total_capex_musd))
c3.metric("CAPEX Penalty", f"{delta_pct:.1f}%", status)

st.progress(min(1.0, max(0.0, result.total_capex_musd / max(optimized_result.total_capex_musd * 1.35, 1e-6))))

st.subheader("Four Main Levers")
l1, l2, l3, l4 = st.columns(4)
l1.metric("WTG capacity", compact_number(result.turbine_mw, "MW"))
l2.metric("Draft", compact_number(result.draft_m, "m"))
l3.metric("Pitch / heel", compact_number(result.static_heel_deg, "deg"), f"limit {result.allowable_pitch_deg:.1f} deg")
l4.metric("Offset", compact_number(result.offset_pct_depth, "% depth"), f"limit {result.allowable_offset_m:.1f} m")

st.subheader("Platform Layout")
d1, d2 = st.columns(2)
with d1:
    st.markdown(platform_top_svg(result), unsafe_allow_html=True)
with d2:
    st.markdown(platform_side_svg(result, max_column_diameter_m), unsafe_allow_html=True)

st.subheader("CAPEX Breakdown")
costs = pd.DataFrame(
    [
        ["WTG supply", result.wtg_capex_musd],
        ["Platform steel and ballast", result.platform_capex_musd],
        ["Mooring and anchors", result.mooring_cost_musd],
        ["Electrical / balance of plant", result.balance_of_plant_musd],
        ["Installation", result.installation_capex_musd],
        ["Total CAPEX", result.total_capex_musd],
    ],
    columns=["Item", "USD million"],
)
st.dataframe(costs, hide_index=True, width="stretch")

st.subheader("What Changed From Manual Inputs")
comparison = pd.DataFrame(
    [
        ["WTG capacity", base_inputs.turbine_mw, result.turbine_mw, "MW"],
        ["Draft", manual_result.draft_m, result.draft_m, "m"],
        ["Pitch / heel", manual_result.static_heel_deg, result.static_heel_deg, "deg"],
        ["Offset", manual_result.offset_pct_depth, result.offset_pct_depth, "% water depth"],
        ["Total CAPEX", manual_result.total_capex_musd, result.total_capex_musd, "USD million"],
    ],
    columns=["Lever", "Manual value", "Selected value", "Unit"],
)
st.dataframe(comparison, hide_index=True, width="stretch")

st.subheader("Constraint Check")
checks = pd.DataFrame(
    [
        ["Column diameter", result.column_diameter_pass, f"{result.column_diameter_m:.1f} m <= {max_column_diameter_m:.1f} m"],
        ["GM", result.gm_pass, f"{result.gm_m:.2f} m >= {gm_min_m:.1f} m"],
        ["Pitch / heel", result.stability_pass, f"{result.static_heel_deg:.2f} deg <= selected limit"],
        ["Port draft", result.port_pass, f"{result.draft_m:.1f} m <= {port_draft_limit_m:.1f} m"],
        ["Offset", result.offset_pass, f"{result.offset_pct_depth:.2f}% <= selected limit"],
        ["Mooring strength", result.mooring_pass, "Screened utilization <= 45%"],
        ["Ballast", result.ballast_pass, "Ballast positive and <75% displacement"],
    ],
    columns=["Constraint", "Pass", "Meaning"],
)
st.dataframe(checks, hide_index=True, width="stretch")

with st.expander("WTG capacity relation used by the optimizer"):
    turbine_table = pd.DataFrame(TURBINE_LIBRARY)
    turbine_table = turbine_table.rename(
        columns={
            "mw": "MW",
            "rotor_diameter_m": "Rotor diameter [m]",
            "hub_height_m": "Hub height [m]",
            "mass_t": "WTG mass [t]",
            "cog_m": "WTG CoG [m]",
            "thrust_mn": "Max thrust [MN]",
        }
    )
    st.dataframe(turbine_table, hide_index=True, width="stretch")

with st.expander("Detailed engineering values"):
    details = pd.DataFrame(
        [
            ["Column diameter", result.column_diameter_m, "m"],
            ["Column spacing", result.column_spacing_m, "m"],
            ["Column height", result.column_height_m, "m"],
            ["Pontoon width", result.pontoon_width_m, "m"],
            ["Pontoon height", result.pontoon_height_m, "m"],
            ["Structural mass", result.structural_mass_t, "t"],
            ["Ballast", result.ballast_t, "t"],
            ["GM", result.gm_m, "m"],
            ["Restoring / heeling", result.restoring_ratio, "-"],
            ["Environmental force", result.environmental_force_mn, "MN"],
            ["Mooring line diameter", result.mooring_line_diameter_mm, "mm"],
            ["Mooring pretension", result.mooring_pretension_t_per_line, "t/line"],
            ["Mooring mass", result.mooring_mass_t, "t"],
            ["CAPEX per MW", result.capex_per_mw_musd, "USD million/MW"],
        ],
        columns=["Parameter", "Value", "Unit"],
    )
    st.dataframe(details, hide_index=True, width="stretch")

st.info(result.notes)

csv = pd.DataFrame([result_as_dict(result)]).to_csv(index=False).encode("utf-8")
st.download_button("Download selected design CSV", data=csv, file_name="floating_wind_capex_result.csv", mime="text/csv")
