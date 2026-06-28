import importlib
import math

import pandas as pd
import streamlit as st

import engine as engine_module


# Streamlit Cloud can rerun app.py while retaining an older imported engine module.
engine_module = importlib.reload(engine_module)
CHAIN_LIBRARY = engine_module.CHAIN_LIBRARY
TURBINE_LIBRARY = engine_module.TURBINE_LIBRARY
design_inputs_from_turbine = engine_module.design_inputs_from_turbine
optimize_capex = engine_module.optimize_capex
result_as_dict = engine_module.result_as_dict
turbine_from_capacity = engine_module.turbine_from_capacity


st.set_page_config(page_title="Floating Wind Foundation CAPEX Optimizer v0.6", layout="wide")


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


def operation_draft_m(result) -> float:
    return getattr(result, "draft_m", getattr(result, "operation_draft_m", 0.0))


def harbor_draft_m(result) -> float:
    return getattr(result, "deballasted_draft_m", operation_draft_m(result))


def central_column_diameter_m(result) -> float:
    return getattr(result, "central_column_diameter_m", 0.8 * result.column_diameter_m)


def fluid_ballast_fill_fraction(result) -> float:
    return getattr(result, "fluid_ballast_fill_fraction", 0.0)


def failed_constraints(result) -> list[str]:
    checks = [
        ("column diameter", result.column_diameter_pass),
        ("GM", result.gm_pass),
        ("pitch / heel", result.stability_pass),
        ("harbor draft", result.port_pass),
        ("offset", result.offset_pass),
        ("mooring strength", result.mooring_pass),
        ("ballast", result.ballast_pass),
    ]
    return [name for name, passed in checks if not passed]


def constraint_margins_for_ui(result, gm_min_m, harbor_draft_limit_m, max_column_diameter_m, mooring_line_count, mooring_safety_factor, mooring_utilization_limit):
    ballast_positive = 0.0 if result.ballast_t > 0 else 1.0 + abs(result.ballast_t) / max(result.buoyancy_t, 1.0)
    harbor_draft = harbor_draft_m(result)
    return {
        "column diameter": (result.column_diameter_m / max(max_column_diameter_m, 1e-6), f"increase max column diameter above {result.column_diameter_m:.1f} m"),
        "GM": (gm_min_m / max(result.gm_m, 1e-6), f"reduce minimum GM below {result.gm_m:.2f} m or allow larger geometry"),
        "pitch / heel": (result.static_heel_deg / max(result.allowable_pitch_deg, 1e-6), f"increase pitch limit above {result.static_heel_deg:.1f} deg or allow larger geometry"),
        "harbor draft": (harbor_draft / max(harbor_draft_limit_m, 1e-6), f"increase harbor draft limit above {harbor_draft:.1f} m"),
        "ballast positive": (ballast_positive, "allow a lighter geometry or revise ballast assumptions"),
        "ballast fraction": (result.ballast_t / max(0.75 * result.buoyancy_t, 1e-6), "allow a higher ballast fraction or revise geometry"),
        "fluid ballast tank capacity": (
            fluid_ballast_fill_fraction(result),
            "allow larger pontoons or additional ballast tanks",
        ),
        "offset": (result.offset_m / max(result.allowable_offset_m, 1e-6), f"increase offset limit above {result.offset_m:.1f} m"),
        "mooring strength": (result.mooring_utilization / max(mooring_utilization_limit, 1e-6), f"increase mooring allowable utilization above {result.mooring_utilization:.2f} or allow stronger mooring"),
    }


def most_restrictive_message(result, gm_min_m, harbor_draft_limit_m, max_column_diameter_m, mooring_line_count, mooring_safety_factor, mooring_utilization_limit) -> str:
    margins = constraint_margins_for_ui(
        result,
        gm_min_m,
        harbor_draft_limit_m,
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
    cx, cy = width / 2, 170
    scale = min(3.0, 145.0 / max(result.column_spacing_m, 1.0))
    radius = result.column_spacing_m * scale
    outer_r = max(8.0, result.column_diameter_m * scale / 2.0)
    central_diameter = central_column_diameter_m(result)
    central_r = max(7.0, central_diameter * scale / 2.0)
    pontoon_width = max(9.0, result.pontoon_width_m * scale)
    points = [
        (cx + radius, cy),
        (cx - 0.5 * radius, cy + math.sqrt(3.0) * radius / 2.0),
        (cx - 0.5 * radius, cy - math.sqrt(3.0) * radius / 2.0),
    ]
    pontoons = "".join(
        f'<line x1="{points[i][0]:.1f}" y1="{points[i][1]:.1f}" '
        f'x2="{cx:.1f}" y2="{cy:.1f}" />'
        for i in range(3)
    )
    struts = "".join(
        f'<line x1="{points[i][0]:.1f}" y1="{points[i][1]:.1f}" '
        f'x2="{cx:.1f}" y2="{cy:.1f}" />'
        for i in range(3)
    )
    cols = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{outer_r:.1f}" />'
        for x, y in points
    )
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="Top view platform layout">
      <style>
        .bg {{ fill:#ffffff; }}
        .radial-pontoon {{ stroke:#ef4444; stroke-width:{pontoon_width:.1f}; stroke-linecap:butt; filter:url(#shadow); }}
        .strut {{ stroke:#facc15; stroke-width:3; stroke-linecap:round; }}
        .column {{ fill:#ef4444; stroke:#b91c1c; stroke-width:2; }}
        .center {{ fill:#f8fafc; stroke:#b91c1c; stroke-width:3; }}
        .dim {{ stroke:#111827; stroke-width:1; marker-start:url(#arrow); marker-end:url(#arrow); }}
        .extension {{ stroke:#64748b; stroke-width:1; }}
        .label {{ font: 13px system-ui, sans-serif; fill:#111827; }}
        .small {{ font: 12px system-ui, sans-serif; fill:#334155; }}
      </style>
      <defs>
        <marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" fill="#111827" />
        </marker>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="4" dy="5" stdDeviation="3" flood-color="#000000" flood-opacity="0.22" />
        </filter>
      </defs>
      <rect class="bg" x="0" y="0" width="{width}" height="{height}" />
      <g class="radial-pontoon">{pontoons}</g>
      <g class="strut">{struts}</g>
      <g class="column">{cols}</g>
      <circle class="center" cx="{cx:.1f}" cy="{cy:.1f}" r="{central_r:.1f}" />
      <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{max(3.0, central_r * 0.32):.1f}" fill="#334155" />
      <line class="extension" x1="{cx:.1f}" y1="{cy+35:.1f}" x2="{cx:.1f}" y2="{cy+64:.1f}" />
      <line class="extension" x1="{points[0][0]:.1f}" y1="{cy+35:.1f}" x2="{points[0][0]:.1f}" y2="{cy+64:.1f}" />
      <line class="dim" x1="{cx:.1f}" y1="{cy+55:.1f}" x2="{points[0][0]:.1f}" y2="{cy+55:.1f}" />
      <text class="label" x="{cx+radius/2-54:.1f}" y="{cy+49:.1f}">{result.column_spacing_m:.1f} m radial spacing</text>
      <line class="dim" x1="{points[0][0]-outer_r:.1f}" y1="{cy-38:.1f}" x2="{points[0][0]+outer_r:.1f}" y2="{cy-38:.1f}" />
      <text class="label" x="{points[0][0]-58:.1f}" y="{cy-49:.1f}">Outer dia {result.column_diameter_m:.1f} m</text>
      <text class="label" x="{cx-112:.1f}" y="{cy-27:.1f}">Central dia {central_diameter:.1f} m</text>
      <text class="small" x="{cx-42:.1f}" y="{cy-52:.1f}">WTG support</text>
      <text class="small" x="20" y="334">Top view: VolturnUS-S four-column radial layout</text>
    </svg>
    """


def platform_side_svg(result, max_column_diameter_m: float, harbor_draft_limit_m: float) -> str:
    width, height = 560, 360
    cx = width / 2
    keel_y = 294
    projected_radius = result.column_spacing_m * math.sqrt(3.0) / 2.0
    col_scale = min(
        5.2,
        205.0 / max(result.column_height_m, 1.0),
        218.0 / max(projected_radius + result.column_diameter_m / 2.0, 1.0),
    )
    col_height_px = result.column_height_m * col_scale
    operation_draft = operation_draft_m(result)
    harbor_draft = harbor_draft_m(result)
    draft_px = operation_draft * col_scale
    freeboard_px = max(0.0, col_height_px - draft_px)
    top_y = keel_y - col_height_px
    water_y = keel_y - draft_px
    harbor_y = keel_y - harbor_draft * col_scale
    outer_w = max(24.0, result.column_diameter_m * col_scale)
    central_w = max(20.0, central_column_diameter_m(result) * col_scale)
    pontoon_h = max(18.0, result.pontoon_height_m * col_scale)
    x1, x2 = cx - projected_radius * col_scale, cx + projected_radius * col_scale
    ratio = min(1.0, result.column_diameter_m / max(max_column_diameter_m, 1e-6))
    fill = "#dc2626" if ratio > 1.0 else "#ef4444"
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="Side view platform layout">
      <style>
        .bg {{ fill:#ffffff; }}
        .waterline {{ stroke:#0f766e; stroke-width:1.5; }}
        .harborline {{ stroke:#0284c7; stroke-width:1; stroke-dasharray:5 4; }}
        .column {{ fill:{fill}; stroke:#b91c1c; stroke-width:2; filter:url(#shadow); }}
        .dry {{ fill:#ecfccb; stroke:#65a30d; stroke-width:2; }}
        .pontoon {{ fill:{fill}; stroke:#b91c1c; stroke-width:2; filter:url(#shadow); }}
        .strut {{ stroke:#475569; stroke-width:3; }}
        .tower {{ stroke:#334155; stroke-width:5; }}
        .dim {{ stroke:#111827; stroke-width:1; marker-start:url(#arrow); marker-end:url(#arrow); }}
        .extension {{ stroke:#64748b; stroke-width:1; }}
        .label {{ font: 13px system-ui, sans-serif; fill:#111827; }}
        .small {{ font: 12px system-ui, sans-serif; fill:#334155; }}
      </style>
      <defs>
        <marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" fill="#111827" />
        </marker>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="4" dy="5" stdDeviation="3" flood-color="#000000" flood-opacity="0.20" />
        </filter>
      </defs>
      <rect class="bg" x="0" y="0" width="{width}" height="{height}" />
      <line class="waterline" x1="48" y1="{water_y}" x2="{width-46}" y2="{water_y}" />
      <line class="harborline" x1="48" y1="{harbor_y:.1f}" x2="{width-46}" y2="{harbor_y:.1f}" />
      <rect class="pontoon" x="{x1-outer_w/2:.1f}" y="{keel_y-pontoon_h:.1f}" width="{cx-x1+outer_w/2:.1f}" height="{pontoon_h:.1f}" rx="3" />
      <rect class="pontoon" x="{cx:.1f}" y="{keel_y-pontoon_h:.1f}" width="{x2-cx+outer_w/2:.1f}" height="{pontoon_h:.1f}" rx="3" />
      <line class="strut" x1="{cx:.1f}" y1="{top_y+5:.1f}" x2="{x1:.1f}" y2="{top_y+5:.1f}" />
      <line class="strut" x1="{cx:.1f}" y1="{top_y+5:.1f}" x2="{x2:.1f}" y2="{top_y+5:.1f}" />
      <rect class="column" x="{x1-outer_w/2:.1f}" y="{water_y:.1f}" width="{outer_w:.1f}" height="{draft_px:.1f}" rx="3" />
      <rect class="column" x="{x2-outer_w/2:.1f}" y="{water_y:.1f}" width="{outer_w:.1f}" height="{draft_px:.1f}" rx="3" />
      <rect class="column" x="{cx-central_w/2:.1f}" y="{water_y:.1f}" width="{central_w:.1f}" height="{draft_px:.1f}" rx="3" />
      <rect class="dry" x="{x1-outer_w/2:.1f}" y="{top_y:.1f}" width="{outer_w:.1f}" height="{freeboard_px:.1f}" rx="3" />
      <rect class="dry" x="{x2-outer_w/2:.1f}" y="{top_y:.1f}" width="{outer_w:.1f}" height="{freeboard_px:.1f}" rx="3" />
      <rect class="dry" x="{cx-central_w/2:.1f}" y="{top_y:.1f}" width="{central_w:.1f}" height="{freeboard_px:.1f}" rx="3" />
      <line class="tower" x1="{cx:.1f}" y1="{top_y:.1f}" x2="{cx:.1f}" y2="{top_y-38:.1f}" />
      <text class="small" x="{cx+10:.1f}" y="{top_y-24:.1f}">WTG tower</text>
      <line class="dim" x1="{x1-outer_w/2-22:.1f}" y1="{top_y:.1f}" x2="{x1-outer_w/2-22:.1f}" y2="{keel_y:.1f}" />
      <text class="label" x="18" y="{top_y-12:.1f}">Column height {result.column_height_m:.1f} m</text>
      <line class="dim" x1="{cx:.1f}" y1="{keel_y+22:.1f}" x2="{x2:.1f}" y2="{keel_y+22:.1f}" />
      <text class="label" x="{cx+(x2-cx)/2-38:.1f}" y="{keel_y+40:.1f}">{result.column_spacing_m:.1f} m radial</text>
      <line class="dim" x1="{width-24:.1f}" y1="{water_y:.1f}" x2="{width-24:.1f}" y2="{keel_y:.1f}" />
      <text class="label" x="{width-158:.1f}" y="{water_y-10:.1f}">Operation draft {operation_draft:.1f} m</text>
      <text class="small" x="{width-190:.1f}" y="{top_y+18:.1f}">Dashed: harbor draft {harbor_draft:.1f} m</text>
      <text class="small" x="{width-190:.1f}" y="{top_y+34:.1f}">Harbor limit {harbor_draft_limit_m:.1f} m</text>
      <text class="small" x="20" y="344">Side view: central tower column, radial columns, bottom pontoons and upper struts</text>
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

st.title("Floating Wind Foundation CAPEX Optimizer v0.6")
st.caption(
    "A concept-screening optimizer anchored to the UMaine VolturnUS-S 15 MW reference platform."
)

with st.sidebar:
    st.header("Constraint")
    allowable_pitch_deg = st.number_input("Pitch limit [deg]", min_value=0.5, max_value=30.0, value=8.0, step=0.5)
    harbor_draft_limit_m = st.number_input("Harbor draft limit [m]", min_value=1.0, max_value=120.0, value=25.0, step=1.0)
    allowable_offset_m = st.number_input("Offset limit [m]", min_value=0.5, max_value=300.0, value=10.0, step=0.5)
    max_column_diameter_m = st.number_input("Max column diameter [m]", min_value=1.0, max_value=60.0, value=15.0, step=0.5)
    gm_min_m = st.number_input("Minimum GM [m]", min_value=0.1, max_value=30.0, value=2.0, step=0.1)
    mooring_utilization_limit = st.number_input("Mooring allowable utilization", min_value=0.05, max_value=1.0, value=0.45, step=0.05)

    st.header("Turbine")
    turbine_mw = st.slider("WTG capacity [MW]", 8.0, 20.0, 15.0, 1.0)
    turbine_props = turbine_from_capacity(turbine_mw)
    st.caption(
        f"Uses table data: rotor {turbine_props['rotor_diameter_m']:.0f} m, "
        f"mass {turbine_props['mass_t']:.0f} t, thrust {turbine_props['thrust_mn']:.2f} MN."
    )

    st.header("Site")
    water_depth_m = st.number_input("Water depth [m]", min_value=1.0, max_value=3000.0, value=200.0, step=10.0)
    tp_s = 12.0
    allowable_offset_m = min(allowable_offset_m, water_depth_m * 0.50)
    allowable_offset_pct_depth = 100.0 * allowable_offset_m / max(water_depth_m, 1e-6)

    mooring_line_count = 3
    mooring_safety_factor = 1.5
    mooring_cost_multiplier = 1.0

base_inputs = design_inputs_from_turbine(
    turbine_mw=turbine_mw,
    water_depth_m=water_depth_m,
    tp_s=tp_s,
    port_draft_limit_m=harbor_draft_limit_m,
    gm_min_m=gm_min_m,
    allowable_pitch_deg=allowable_pitch_deg,
    mooring_line_count=mooring_line_count,
    mooring_utilization_limit=mooring_utilization_limit,
    allowable_offset_pct_depth=allowable_offset_pct_depth,
    mooring_safety_factor=mooring_safety_factor,
    mooring_cost_multiplier=mooring_cost_multiplier,
    max_column_diameter_m=max_column_diameter_m,
)

optimized_result = optimize_capex(base_inputs, False, False, False, False)
result = optimized_result
status = "PASS" if result.overall_pass else "NOT PASS"
capex_label = "Minimum Foundation CAPEX" if result.overall_pass else "Best Available Foundation CAPEX"

c1, c2, c3 = st.columns([1.2, 1, 1])
c1.metric(capex_label, money_musd(result.total_capex_musd))
c2.metric("Foundation CAPEX / MW", money_musd(result.capex_per_mw_musd))
c3.metric("Feasibility", status)

st.progress(1.0 if result.overall_pass else 0.35)

if not result.overall_pass:
    blockers = ", ".join(failed_constraints(result))
    relax = most_restrictive_message(
        result,
        gm_min_m,
        harbor_draft_limit_m,
        max_column_diameter_m,
        mooring_line_count,
        mooring_safety_factor,
        mooring_utilization_limit,
    )
    st.error(
        "No feasible design was found within the current search range and constraints. "
        f"The displayed result is the closest diagnostic candidate, blocked by: {blockers}. {relax}"
    )

st.subheader("Key Results")
l1, l2, l3, l4 = st.columns(4)
operation_draft = operation_draft_m(result)
harbor_draft = harbor_draft_m(result)
l1.metric("WTG capacity", compact_number(result.turbine_mw, "MW"))
l2.metric("Operation draft", compact_number(operation_draft, "m"), f"harbor {harbor_draft:.1f} m / limit {harbor_draft_limit_m:.1f} m")
l3.metric("Pitch / heel", compact_number(result.static_heel_deg, "deg"), f"limit {result.allowable_pitch_deg:.1f} deg")
l4.metric("Offset", compact_number(result.offset_m, "m"), f"limit {result.allowable_offset_m:.1f} m")

st.subheader("Platform Layout")
st.caption(
    "VolturnUS-S arrangement with the WTG on the central column. Mooring lines are not visualized."
)
d1, d2 = st.columns(2)
with d1:
    st.markdown(platform_top_svg(result), unsafe_allow_html=True)
with d2:
    st.markdown(platform_side_svg(result, max_column_diameter_m, harbor_draft_limit_m), unsafe_allow_html=True)

st.subheader("CAPEX Breakdown")
costs = pd.DataFrame(
    [
        ["Platform steel and ballast", result.platform_capex_musd],
        ["Mooring and anchors", result.mooring_cost_musd],
        ["Electrical / balance of plant", result.balance_of_plant_musd],
        ["Installation", result.installation_capex_musd],
        ["Foundation CAPEX", result.total_capex_musd],
    ],
    columns=["Item", "USD million"],
)
st.dataframe(costs, hide_index=True, width="stretch")

st.subheader("Optimized Geometry")
comparison = pd.DataFrame(
    [
        ["Radial column spacing", result.column_spacing_m, "m"],
        ["Outer column diameter", result.column_diameter_m, "m"],
        ["Central column diameter", central_column_diameter_m(result), "m"],
        ["Operation draft", operation_draft, "m"],
        ["Deballasted harbor draft", harbor_draft, "m"],
        ["Pontoon width", result.pontoon_width_m, "m"],
        ["Pontoon height", result.pontoon_height_m, "m"],
        ["Fluid ballast fill", 100.0 * fluid_ballast_fill_fraction(result), "% pontoon volume"],
        ["Foundation CAPEX", result.total_capex_musd, "USD million"],
    ],
    columns=["Design variable", "Optimized value", "Unit"],
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

with st.expander("VolturnUS-S reference values"):
    reference_table = pd.DataFrame(
        [
            ["Outer radial columns", 3, "-"],
            ["Outer column diameter", 12.5, "m"],
            ["Central column diameter", 10.0, "m"],
            ["Radial column spacing", 51.75, "m"],
            ["Pontoon width", 12.5, "m"],
            ["Pontoon height", 7.0, "m"],
            ["Operation draft", 20.0, "m"],
            ["Freeboard", 15.0, "m"],
            ["Hull displacement", 20206, "m3"],
            ["Hull steel mass", 3914, "t"],
            ["Fixed ballast", 2540, "t"],
            ["Fluid ballast", 11300, "t"],
            ["Tower interface", 100, "t"],
        ],
        columns=["Reference parameter", "Value", "Unit"],
    )
    st.dataframe(reference_table, hide_index=True, width="stretch")
    st.caption("Source: NREL/TP-5000-76773, Definition of the UMaine VolturnUS-S Reference Platform.")

with st.expander("Mooring chain property table used for screening"):
    chain_table = pd.DataFrame(CHAIN_LIBRARY)
    chain_table = chain_table.rename(
        columns={
            "diameter_mm": "Diameter [mm]",
            "mass_t_per_m": "Mass [t/m]",
            "mbl_mn": "MBL [MN]",
        }
    )
    st.dataframe(chain_table, hide_index=True, width="stretch")

with st.expander("Detailed engineering values"):
    details = pd.DataFrame(
        [
            ["Outer column diameter", result.column_diameter_m, "m"],
            ["Central column diameter", central_column_diameter_m(result), "m"],
            ["Radial column spacing", result.column_spacing_m, "m"],
            ["Column height", result.column_height_m, "m"],
            ["Pontoon width", result.pontoon_width_m, "m"],
            ["Pontoon height", result.pontoon_height_m, "m"],
            ["Operation draft", operation_draft, "m"],
            ["Deballasted harbor draft", harbor_draft, "m"],
            ["Structural mass", result.structural_mass_t, "t"],
            ["Tower interface mass", getattr(result, "tower_interface_mass_t", 0.0), "t"],
            ["Fixed ballast", getattr(result, "fixed_ballast_t", 0.0), "t"],
            ["Fluid ballast", getattr(result, "fluid_ballast_t", result.ballast_t), "t"],
            ["Fluid ballast volume", getattr(result, "fluid_ballast_volume_m3", 0.0), "m3"],
            ["Pontoon ballast volume", getattr(result, "pontoon_volume_m3", 0.0), "m3"],
            ["Fluid ballast fill", 100.0 * fluid_ballast_fill_fraction(result), "%"],
            ["Operational mooring vertical load equivalent", getattr(result, "mooring_vertical_load_t", 0.0), "t"],
            ["GM", result.gm_m, "m"],
            ["Restoring / heeling", result.restoring_ratio, "-"],
            ["Mooring demand (rotor thrust)", result.mooring_demand_mn, "MN"],
            ["Mooring line diameter", result.mooring_line_diameter_mm, "mm"],
            ["Mooring fairlead tension", result.mooring_fairlead_tension_mn, "MN"],
            ["Mooring utilization", result.mooring_utilization, "-"],
            ["Mooring mass", result.mooring_mass_t, "t"],
            ["CAPEX per MW", result.capex_per_mw_musd, "USD million/MW"],
        ],
        columns=["Parameter", "Value", "Unit"],
    )
    st.dataframe(details, hide_index=True, width="stretch")

st.info(result.notes)

csv = pd.DataFrame([result_as_dict(result)]).to_csv(index=False).encode("utf-8")
st.download_button("Download selected design CSV", data=csv, file_name="floating_wind_capex_result.csv", mime="text/csv")
