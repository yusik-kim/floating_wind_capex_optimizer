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


st.set_page_config(page_title="Floating Wind Foundation CAPEX Optimizer v0.5", layout="wide")


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


def failed_constraints(result) -> list[str]:
    checks = [
        ("column diameter", result.column_diameter_pass),
        ("GM", result.gm_pass),
        ("pitch / heel", result.stability_pass),
        ("port draft", result.port_pass),
        ("offset", result.offset_pass),
        ("mooring strength", result.mooring_pass),
        ("ballast", result.ballast_pass),
    ]
    return [name for name, passed in checks if not passed]


def constraint_margins_for_ui(result, gm_min_m, restoring_ratio_min, port_draft_limit_m, max_column_diameter_m, mooring_line_count, mooring_safety_factor, mooring_utilization_limit):
    mooring_mbl = 0.00055 * result.mooring_line_diameter_mm**2
    mooring_utilization = result.environmental_force_mn * mooring_safety_factor / max(mooring_line_count * mooring_mbl, 1e-6)
    ballast_positive = 0.0 if result.ballast_t > 0 else 1.0 + abs(result.ballast_t) / max(result.buoyancy_t, 1.0)
    return {
        "column diameter": (result.column_diameter_m / max(max_column_diameter_m, 1e-6), f"increase max column diameter above {result.column_diameter_m:.1f} m"),
        "GM": (gm_min_m / max(result.gm_m, 1e-6), f"reduce minimum GM below {result.gm_m:.2f} m or allow larger geometry"),
        "pitch / heel": (result.static_heel_deg / max(result.allowable_pitch_deg, 1e-6), f"increase pitch limit above {result.static_heel_deg:.1f} deg or allow larger geometry"),
        "restoring ratio": (restoring_ratio_min / max(result.restoring_ratio, 1e-6), f"reduce restoring ratio below {result.restoring_ratio:.2f} or allow larger geometry"),
        "port draft": (result.draft_m / max(port_draft_limit_m, 1e-6), f"increase port draft limit above {result.draft_m:.1f} m"),
        "ballast positive": (ballast_positive, "allow a lighter geometry or revise ballast assumptions"),
        "ballast fraction": (result.ballast_t / max(0.75 * result.buoyancy_t, 1e-6), "allow a higher ballast fraction or revise geometry"),
        "offset": (result.offset_m / max(result.allowable_offset_m, 1e-6), f"increase offset limit above {result.offset_m:.1f} m"),
        "mooring strength": (mooring_utilization / max(mooring_utilization_limit, 1e-6), f"increase mooring allowable utilization above {mooring_utilization:.2f} or allow stronger mooring"),
    }


def most_restrictive_message(result, gm_min_m, restoring_ratio_min, port_draft_limit_m, max_column_diameter_m, mooring_line_count, mooring_safety_factor, mooring_utilization_limit) -> str:
    margins = constraint_margins_for_ui(
        result,
        gm_min_m,
        restoring_ratio_min,
        port_draft_limit_m,
        max_column_diameter_m,
        mooring_line_count,
        mooring_safety_factor,
        mooring_utilization_limit,
    )
    failed = {name: data for name, data in margins.items() if data[0] > 1.0}
    if not failed:
        return "No failed physical constraint."
    name, (margin, advice) = max(failed.items(), key=lambda item: item[1][0])
    return f"Most restrictive constraint: {name} ({margin:.2f}x limit). Try to {advice}."


def platform_top_svg(result) -> str:
    width, height = 560, 360
    cx, cy = width / 2, height / 2
    scale = min(2.25, 150.0 / max(result.column_spacing_m, 1.0))
    radius = result.column_spacing_m / math.sqrt(3.0) * scale
    col_r = max(8.0, result.column_diameter_m * scale / 2.0)
    points = [
        (cx + radius, cy),
        (cx - 0.5 * radius, cy + math.sqrt(3.0) * radius / 2.0),
        (cx - 0.5 * radius, cy - math.sqrt(3.0) * radius / 2.0),
    ]
    arms = "".join(
        f'<line x1="{points[i][0]:.1f}" y1="{points[i][1]:.1f}" '
        f'x2="{cx:.1f}" y2="{cy:.1f}" />'
        for i in range(3)
    )
    cols = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{col_r:.1f}" />'
        for x, y in points
    )
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="Top view platform layout">
      <style>
        .bg {{ fill:#ffffff; }}
        .arm {{ stroke:#ef4444; stroke-width:15; stroke-linecap:round; filter:url(#shadow); }}
        .column {{ fill:#ef4444; stroke:#b91c1c; stroke-width:2; }}
        .center {{ fill:#ffffff; stroke:#ef4444; stroke-width:5; }}
        .dim {{ stroke:#111827; stroke-width:1; marker-start:url(#arrow); marker-end:url(#arrow); }}
        .thin {{ stroke:#111827; stroke-width:1; fill:none; }}
        .label {{ font: 13px system-ui, sans-serif; fill:#111827; }}
        .small {{ font: 12px system-ui, sans-serif; fill:#334155; }}
      </style>
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#111827" />
        </marker>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="4" dy="5" stdDeviation="3" flood-color="#000000" flood-opacity="0.22" />
        </filter>
      </defs>
      <rect class="bg" x="0" y="0" width="{width}" height="{height}" />
      <g class="arm">{arms}</g>
      <g class="column">{cols}</g>
      <circle class="center" cx="{cx:.1f}" cy="{cy:.1f}" r="{max(7.0, col_r * 0.65):.1f}" />
      <line class="dim" x1="{points[2][0]:.1f}" y1="{points[2][1]-28:.1f}" x2="{points[0][0]:.1f}" y2="{points[0][1]-28:.1f}" />
      <text class="label" x="{(points[2][0]+points[0][0])/2-20:.1f}" y="{points[0][1]-38:.1f}">{result.column_spacing_m:.1f} m</text>
      <text class="label" x="{points[2][0]-54:.1f}" y="{points[2][1]-8:.1f}">Dia {result.column_diameter_m:.1f} m</text>
      <text class="small" x="20" y="334">Top view: 3-column semi-sub layout</text>
    </svg>
    """


def platform_side_svg(result, max_column_diameter_m: float, port_draft_limit_m: float) -> str:
    width, height = 560, 360
    water_y = 202
    keel_y = 304
    available_height = 220.0
    col_scale = available_height / max(result.column_height_m, 1.0)
    col_height_px = result.column_height_m * col_scale
    draft_px = result.draft_m * col_scale
    freeboard_px = max(0.0, col_height_px - draft_px)
    top_y = keel_y - col_height_px
    water_y = keel_y - draft_px
    col_w = max(30.0, min(72.0, result.column_diameter_m * 4.0))
    spacing_px = min(330.0, max(190.0, result.column_spacing_m * 3.0))
    x1, x2 = width / 2 - spacing_px / 2, width / 2 + spacing_px / 2
    ratio = min(1.0, result.column_diameter_m / max(max_column_diameter_m, 1e-6))
    fill = "#dc2626" if ratio > 1.0 else "#ef4444"
    pontoon_h = 22
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="Side view platform layout">
      <style>
        .bg {{ fill:#ffffff; }}
        .waterline {{ stroke:#111827; stroke-width:1; }}
        .column {{ fill:{fill}; stroke:#b91c1c; stroke-width:2; filter:url(#shadow); }}
        .dry {{ fill:#ffffff; stroke:#84cc16; stroke-width:4; }}
        .pontoon {{ fill:{fill}; stroke:#b91c1c; stroke-width:2; filter:url(#shadow); }}
        .dim {{ stroke:#111827; stroke-width:1; marker-start:url(#arrow); marker-end:url(#arrow); }}
        .thin {{ stroke:#111827; stroke-width:1; fill:none; }}
        .label {{ font: 13px system-ui, sans-serif; fill:#111827; }}
        .small {{ font: 12px system-ui, sans-serif; fill:#334155; }}
      </style>
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#111827" />
        </marker>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="4" dy="5" stdDeviation="3" flood-color="#000000" flood-opacity="0.20" />
        </filter>
      </defs>
      <rect class="bg" x="0" y="0" width="{width}" height="{height}" />
      <line class="waterline" x1="48" y1="{water_y}" x2="{width-46}" y2="{water_y}" />
      <rect class="pontoon" x="{x1-col_w/2:.1f}" y="{keel_y-pontoon_h:.1f}" width="{x2-x1+col_w:.1f}" height="{pontoon_h}" rx="3" />
      <rect class="column" x="{x1-col_w/2:.1f}" y="{water_y:.1f}" width="{col_w:.1f}" height="{draft_px:.1f}" rx="4" />
      <rect class="column" x="{x2-col_w/2:.1f}" y="{water_y:.1f}" width="{col_w:.1f}" height="{draft_px:.1f}" rx="4" />
      <rect class="dry" x="{x1-col_w/2:.1f}" y="{top_y:.1f}" width="{col_w:.1f}" height="{freeboard_px:.1f}" rx="4" />
      <rect class="dry" x="{x2-col_w/2:.1f}" y="{top_y:.1f}" width="{col_w:.1f}" height="{freeboard_px:.1f}" rx="4" />
      <line class="dim" x1="{x1-col_w/2-42:.1f}" y1="{top_y:.1f}" x2="{x1-col_w/2-42:.1f}" y2="{keel_y:.1f}" />
      <text class="label" x="{x1-col_w/2-112:.1f}" y="{(top_y+keel_y)/2+4:.1f}">{result.column_height_m:.1f} m column</text>
      <line class="dim" x1="{x1:.1f}" y1="{keel_y+28:.1f}" x2="{x2:.1f}" y2="{keel_y+28:.1f}" />
      <text class="label" x="{width/2-28:.1f}" y="{keel_y+45:.1f}">{result.column_spacing_m:.1f} m</text>
      <line class="dim" x1="{x2+42:.1f}" y1="{water_y:.1f}" x2="{x2+42:.1f}" y2="{keel_y:.1f}" />
      <text class="label" x="{x2+52:.1f}" y="{(water_y+keel_y)/2-4:.1f}">{result.draft_m:.1f} m draft</text>
      <text class="small" x="{x2+52:.1f}" y="{(water_y+keel_y)/2+14:.1f}">limit {port_draft_limit_m:.1f} m</text>
      <line class="dim" x1="{x1-col_w/2:.1f}" y1="{keel_y+10:.1f}" x2="{x1+col_w/2:.1f}" y2="{keel_y+10:.1f}" />
      <text class="label" x="{x1-col_w/2-2:.1f}" y="{keel_y+24:.1f}">{result.column_diameter_m:.1f} m</text>
      <text class="small" x="20" y="334">Side view: foundation geometry only</text>
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

st.title("Floating Wind Foundation CAPEX Optimizer v0.5")
st.caption("A concept-screening optimizer for non-experts: choose turbine size, then optimize foundation CAPEX excluding WTG supply cost.")

with st.sidebar:
    st.header("Minimize Foundation CAPEX")
    optimize_draft = st.toggle("Optimize draft", value=True)
    if optimize_draft:
        target_draft_m = 20.0
    else:
        target_draft_m = st.slider("Draft [m]", 14.0, 28.0, 20.0, 1.0)

    st.header("Turbine")
    turbine_mw = st.slider("WTG capacity [MW]", 8.0, 20.0, 15.0, 1.0)
    turbine_props = turbine_from_capacity(turbine_mw)
    st.caption(
        f"Uses table data: rotor {turbine_props['rotor_diameter_m']:.0f} m, "
        f"mass {turbine_props['mass_t']:.0f} t, thrust {turbine_props['thrust_mn']:.2f} MN."
    )

    st.header("Site")
    water_depth_m = st.number_input("Water depth [m]", 40.0, 1500.0, 200.0, 10.0)
    hs_m = st.number_input("Significant wave height Hs [m]", 1.0, 20.0, 8.0, 0.5)
    tp_s = 12.0

    st.header("Constraint")
    allowable_pitch_deg = st.number_input("Pitch limit [deg]", 2.0, 15.0, 8.0, 0.5)
    port_draft_limit_m = st.number_input("Port draft limit [m]", 5.0, 80.0, 25.0, 1.0)
    max_offset_slider = max(5.0, min(120.0, water_depth_m * 0.50))
    allowable_offset_m = st.number_input("Offset limit [m]", 1.0, max_offset_slider, min(10.0, max_offset_slider), 1.0)
    allowable_offset_pct_depth = 100.0 * allowable_offset_m / max(water_depth_m, 1e-6)
    max_column_diameter_m = st.number_input("Max column diameter [m]", 6.0, 30.0, 15.0, 0.5)
    gm_min_m = st.number_input("Minimum GM [m]", 0.5, 10.0, 2.0, 0.5)
    mooring_utilization_limit = st.number_input("Mooring allowable utilization", 0.2, 0.8, 0.45, 0.05)
    restoring_ratio_min = 1.3
    mooring_line_count = 3
    mooring_safety_factor = 1.5
    mooring_cost_multiplier = 1.0

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
    mooring_utilization_limit=mooring_utilization_limit,
    allowable_offset_pct_depth=allowable_offset_pct_depth,
    mooring_safety_factor=mooring_safety_factor,
    mooring_cost_multiplier=mooring_cost_multiplier,
    max_column_diameter_m=max_column_diameter_m,
    target_draft_m=target_draft_m,
)

optimized_result = optimize_capex(base_inputs, False, True, False, False)
result = optimize_capex(base_inputs, False, optimize_draft, False, False)
manual_result = evaluate_semisub(base_inputs)

delta_musd = result.total_capex_musd - optimized_result.total_capex_musd
delta_pct = 100.0 * delta_musd / max(optimized_result.total_capex_musd, 1e-6)
status = "PASS" if result.overall_pass else "CHECK"
selected_label = "Selected Foundation CAPEX" if result.overall_pass else "Best Available Foundation CAPEX"
optimized_label = "Optimized Foundation CAPEX" if optimized_result.overall_pass else "Best Available Foundation CAPEX"
delta_label = f"{money_musd(delta_musd)} vs feasible optimum" if optimized_result.overall_pass else "no feasible optimum"

c1, c2, c3 = st.columns([1.2, 1, 1])
c1.metric(selected_label, money_musd(result.total_capex_musd), delta_label)
c2.metric(optimized_label, money_musd(optimized_result.total_capex_musd))
c3.metric("CAPEX Delta", f"{delta_pct:.1f}%", status)

st.progress(min(1.0, max(0.0, result.total_capex_musd / max(optimized_result.total_capex_musd * 1.35, 1e-6))))

if not optimized_result.overall_pass:
    blockers = ", ".join(failed_constraints(optimized_result))
    relax = most_restrictive_message(
        optimized_result,
        gm_min_m,
        restoring_ratio_min,
        port_draft_limit_m,
        max_column_diameter_m,
        mooring_line_count,
        mooring_safety_factor,
        mooring_utilization_limit,
    )
    st.error(
        "No feasible design was found within the current search range and constraints. "
        f"The displayed result is the closest diagnostic candidate, blocked by: {blockers}. {relax}"
    )
elif not result.overall_pass:
    blockers = ", ".join(failed_constraints(result))
    relax = most_restrictive_message(
        result,
        gm_min_m,
        restoring_ratio_min,
        port_draft_limit_m,
        max_column_diameter_m,
        mooring_line_count,
        mooring_safety_factor,
        mooring_utilization_limit,
    )
    st.warning(
        "The selected manual settings do not satisfy all constraints. "
        f"Blocking checks: {blockers}. {relax}"
    )

st.subheader("Four Main Levers")
l1, l2, l3, l4 = st.columns(4)
l1.metric("WTG capacity", compact_number(result.turbine_mw, "MW"))
l2.metric("Draft", compact_number(result.draft_m, "m"), f"limit {port_draft_limit_m:.1f} m")
l3.metric("Pitch / heel", compact_number(result.static_heel_deg, "deg"), f"limit {result.allowable_pitch_deg:.1f} deg")
l4.metric("Offset", compact_number(result.offset_m, "m"), f"limit {result.allowable_offset_m:.1f} m")

st.subheader("Platform Layout")
d1, d2 = st.columns(2)
with d1:
    st.markdown(platform_top_svg(result), unsafe_allow_html=True)
with d2:
    st.markdown(platform_side_svg(result, max_column_diameter_m, port_draft_limit_m), unsafe_allow_html=True)

st.subheader("CAPEX Breakdown")
costs = pd.DataFrame(
    [
        ["Platform steel and ballast", result.platform_capex_musd],
        ["Mooring and anchors", result.mooring_cost_musd],
        ["Electrical / balance of plant", result.balance_of_plant_musd],
        ["Installation", result.installation_capex_musd],
        ["Foundation CAPEX excl. WTG supply", result.total_capex_musd],
        ["WTG supply shown separately", result.wtg_capex_musd],
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
        ["Offset", manual_result.offset_m, result.offset_m, "m"],
        ["Foundation CAPEX", manual_result.total_capex_musd, result.total_capex_musd, "USD million"],
    ],
    columns=["Lever", "Manual value", "Selected value", "Unit"],
)
st.dataframe(comparison, hide_index=True, width="stretch")

with st.expander("WTG capacity relation used for sizing loads"):
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
