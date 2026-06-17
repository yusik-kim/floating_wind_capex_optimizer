"""
Floating Wind Foundation CAPEX Optimizer v0.5
Semi-sub template modules 1-5:
1) Template platform scaling
2) Weight estimation
3) Hydrostatic analysis
4) Static stability analysis
5) Mooring and offset screening

Concept-level screening only. Not certification or FEED design.
"""
from dataclasses import dataclass, asdict, replace
import math

RHO_SEAWATER_T_PER_M3 = 1.025
G = 9.81
USD_PER_T_STEEL = 5200.0
USD_PER_T_BALLAST = 140.0
USD_PER_T_CHAIN = 4600.0
USD_PER_MW_WTG = 1_250_000.0
USD_PER_MW_ELECTRICAL = 260_000.0
USD_INSTALL_BASE = 8_000_000.0
STEEL_DENSITY_T_PER_M3 = 7.85


TURBINE_LIBRARY = [
    {"mw": 8.0, "rotor_diameter_m": 170.0, "hub_height_m": 115.0, "mass_t": 1150.0, "cog_m": 62.0, "thrust_mn": 1.25},
    {"mw": 10.0, "rotor_diameter_m": 190.0, "hub_height_m": 125.0, "mass_t": 1450.0, "cog_m": 68.0, "thrust_mn": 1.55},
    {"mw": 12.0, "rotor_diameter_m": 220.0, "hub_height_m": 138.0, "mass_t": 1800.0, "cog_m": 74.0, "thrust_mn": 2.05},
    {"mw": 15.0, "rotor_diameter_m": 240.0, "hub_height_m": 150.0, "mass_t": 2200.0, "cog_m": 80.0, "thrust_mn": 2.50},
    {"mw": 18.0, "rotor_diameter_m": 270.0, "hub_height_m": 165.0, "mass_t": 2750.0, "cog_m": 90.0, "thrust_mn": 3.15},
    {"mw": 20.0, "rotor_diameter_m": 290.0, "hub_height_m": 175.0, "mass_t": 3200.0, "cog_m": 98.0, "thrust_mn": 3.65},
]


# Catalogue-style offshore chain properties used for concept screening.
# MBL values are representative of high-strength offshore mooring chain
# and should be replaced with project/vendor data for design work.
CHAIN_LIBRARY = [
    {"diameter_mm": 76.0, "mass_t_per_m": 0.113, "mbl_mn": 6.00},
    {"diameter_mm": 84.0, "mass_t_per_m": 0.138, "mbl_mn": 7.21},
    {"diameter_mm": 92.0, "mass_t_per_m": 0.165, "mbl_mn": 8.50},
    {"diameter_mm": 102.0, "mass_t_per_m": 0.203, "mbl_mn": 10.22},
    {"diameter_mm": 114.0, "mass_t_per_m": 0.253, "mbl_mn": 12.42},
    {"diameter_mm": 127.0, "mass_t_per_m": 0.315, "mbl_mn": 14.96},
    {"diameter_mm": 140.0, "mass_t_per_m": 0.382, "mbl_mn": 17.61},
    {"diameter_mm": 152.0, "mass_t_per_m": 0.451, "mbl_mn": 20.16},
    {"diameter_mm": 162.0, "mass_t_per_m": 0.512, "mbl_mn": 22.32},
    {"diameter_mm": 177.0, "mass_t_per_m": 0.611, "mbl_mn": 25.62},
    {"diameter_mm": 190.0, "mass_t_per_m": 0.704, "mbl_mn": 28.49},
    {"diameter_mm": 203.0, "mass_t_per_m": 0.804, "mbl_mn": 31.34},
    {"diameter_mm": 220.0, "mass_t_per_m": 0.944, "mbl_mn": 35.01},
    {"diameter_mm": 240.0, "mass_t_per_m": 1.123, "mbl_mn": 39.14},
    {"diameter_mm": 260.0, "mass_t_per_m": 1.318, "mbl_mn": 42.97},
]


@dataclass
class SemiSubTemplate:
    name: str = "Generic 3-column semi-sub, 15 MW reference"
    ref_mw: float = 15.0
    ref_rotor_diameter_m: float = 240.0
    n_columns: int = 3
    column_diameter_m: float = 12.0
    column_spacing_m: float = 72.0
    column_height_m: float = 34.0
    pontoon_width_m: float = 10.0
    pontoon_height_m: float = 8.0
    draft_m: float = 20.0
    structural_mass_t: float = 6500.0
    structural_cog_above_keel_m: float = 11.0


@dataclass
class DesignInputs:
    turbine_mw: float
    rotor_diameter_m: float
    hub_height_above_keel_m: float
    wtg_mass_t: float
    wtg_cog_above_keel_m: float
    max_thrust_mn: float
    water_depth_m: float
    hs_m: float
    tp_s: float
    port_draft_limit_m: float
    gm_min_m: float = 2.0
    allowable_pitch_deg: float = 8.0
    mooring_line_count: int = 3
    mooring_utilization_limit: float = 0.45
    allowable_offset_pct_depth: float = 5.0
    mooring_safety_factor: float = 1.5
    mooring_cost_multiplier: float = 1.0
    max_column_diameter_m: float = 15.0
    target_draft_m: float | None = None


@dataclass
class SemiSubResult:
    template: str
    turbine_mw: float
    allowable_pitch_deg: float
    allowable_offset_pct_depth: float
    column_diameter_m: float
    column_spacing_m: float
    column_height_m: float
    pontoon_width_m: float
    pontoon_height_m: float
    draft_m: float
    structural_mass_t: float
    displacement_t: float
    buoyancy_t: float
    ballast_t: float
    total_mass_t: float
    kb_m: float
    bm_m: float
    kg_m: float
    gm_m: float
    heeling_moment_mnm: float
    restoring_moment_mnm: float
    restoring_ratio: float
    static_heel_deg: float
    environmental_force_mn: float
    wave_drift_force_mn: float
    allowable_offset_m: float
    mooring_required_stiffness_mn_per_m: float
    mooring_stiffness_mn_per_m: float
    offset_m: float
    offset_pct_depth: float
    mooring_line_diameter_mm: float
    mooring_line_length_m: float
    mooring_fairlead_tension_mn: float
    mooring_pretension_t_per_line: float
    mooring_utilization: float
    mooring_mass_t: float
    mooring_cost_musd: float
    platform_capex_musd: float
    wtg_capex_musd: float
    foundation_capex_musd: float
    balance_of_plant_musd: float
    installation_capex_musd: float
    total_capex_musd: float
    capex_per_mw_musd: float
    gm_pass: bool
    stability_pass: bool
    port_pass: bool
    ballast_pass: bool
    column_diameter_pass: bool
    offset_pass: bool
    mooring_pass: bool
    overall_pass: bool
    notes: str


def turbine_from_capacity(turbine_mw: float) -> dict:
    """Interpolate concept-level WTG properties from a small reference table."""
    points = TURBINE_LIBRARY
    if turbine_mw <= points[0]["mw"]:
        lo, hi = points[0], points[1]
    elif turbine_mw >= points[-1]["mw"]:
        lo, hi = points[-2], points[-1]
    else:
        lo, hi = points[0], points[-1]
        for idx in range(len(points) - 1):
            if points[idx]["mw"] <= turbine_mw <= points[idx + 1]["mw"]:
                lo, hi = points[idx], points[idx + 1]
                break

    span = hi["mw"] - lo["mw"]
    f = 0.0 if span == 0 else (turbine_mw - lo["mw"]) / span
    out = {"mw": turbine_mw}
    for key in ["rotor_diameter_m", "hub_height_m", "mass_t", "cog_m", "thrust_mn"]:
        out[key] = lo[key] + f * (hi[key] - lo[key])
    return out


def design_inputs_from_turbine(
    turbine_mw: float,
    water_depth_m: float,
    hs_m: float,
    tp_s: float,
    port_draft_limit_m: float,
    gm_min_m: float = 2.0,
    allowable_pitch_deg: float = 8.0,
    mooring_line_count: int = 3,
    mooring_utilization_limit: float = 0.45,
    allowable_offset_pct_depth: float = 5.0,
    mooring_safety_factor: float = 1.5,
    mooring_cost_multiplier: float = 1.0,
    max_column_diameter_m: float = 15.0,
    target_draft_m: float | None = None,
) -> DesignInputs:
    turbine = turbine_from_capacity(turbine_mw)
    return DesignInputs(
        turbine_mw=turbine_mw,
        rotor_diameter_m=turbine["rotor_diameter_m"],
        hub_height_above_keel_m=turbine["hub_height_m"],
        wtg_mass_t=turbine["mass_t"],
        wtg_cog_above_keel_m=turbine["cog_m"],
        max_thrust_mn=turbine["thrust_mn"],
        water_depth_m=water_depth_m,
        hs_m=hs_m,
        tp_s=tp_s,
        port_draft_limit_m=port_draft_limit_m,
        gm_min_m=gm_min_m,
        allowable_pitch_deg=allowable_pitch_deg,
        mooring_line_count=mooring_line_count,
        mooring_utilization_limit=mooring_utilization_limit,
        allowable_offset_pct_depth=allowable_offset_pct_depth,
        mooring_safety_factor=mooring_safety_factor,
        mooring_cost_multiplier=mooring_cost_multiplier,
        max_column_diameter_m=max_column_diameter_m,
        target_draft_m=target_draft_m,
    )


def _component_volumes(n: int, col_dia: float, spacing: float, pontoon_w: float, pontoon_h: float, draft: float):
    column_vol = n * math.pi * (col_dia / 2.0) ** 2 * draft
    # three pontoons forming a triangular ring; first-order screening only
    pontoon_vol = n * spacing * pontoon_w * pontoon_h
    return column_vol, pontoon_vol


def _structural_mass_from_geometry(
    template: SemiSubTemplate,
    col_dia: float,
    spacing: float,
    col_height: float,
    pontoon_w: float,
    pontoon_h: float,
) -> float:
    """Estimate steel mass from a simple wetted-surface / member-size proxy."""
    ref_proxy = (
        template.n_columns * math.pi * template.column_diameter_m * template.column_height_m
        + template.n_columns * template.column_spacing_m * 2.0 * (template.pontoon_width_m + template.pontoon_height_m)
    )
    proxy = (
        template.n_columns * math.pi * col_dia * col_height
        + template.n_columns * spacing * 2.0 * (pontoon_w + pontoon_h)
    )
    return template.structural_mass_t * (proxy / max(ref_proxy, 1e-6)) ** 1.08


def _waterplane_inertia(n: int, col_dia: float, spacing: float) -> float:
    """Approximate waterplane second moment about platform centreline [m4]."""
    area = math.pi * (col_dia / 2.0) ** 2
    local_i = math.pi * (col_dia / 2.0) ** 4 / 4.0
    radius = spacing / math.sqrt(3.0)
    # column coordinates for triangular layout
    coords = [(radius, 0.0), (-0.5 * radius, math.sqrt(3)/2 * radius), (-0.5 * radius, -math.sqrt(3)/2 * radius)]
    # use inertia about y-axis: sum(I_local + A*x^2)
    return sum(local_i + area * x**2 for x, _ in coords[:n])


def _catenary_horizontal_tension(
    submerged_weight_mn_per_m: float,
    line_length_m: float,
    horizontal_span_m: float,
    fairlead_height_m: float,
) -> tuple[float, float]:
    """Return horizontal tension and fairlead tension for a suspended catenary line.

    The line is treated as a flexible inextensible catenary between anchor and fairlead.
    This is still a screening model, but the force-offset behavior comes from catenary
    equilibrium rather than a fitted scalar stiffness.
    """
    horizontal_span_m = max(1.0, horizontal_span_m)
    fairlead_height_m = max(0.1, fairlead_height_m)
    straight_length = math.hypot(horizontal_span_m, fairlead_height_m)
    if line_length_m <= straight_length:
        # Near-taut fallback. A full model would include axial stiffness EA.
        excess = max(0.01, straight_length - line_length_m)
        horizontal_tension = submerged_weight_mn_per_m * straight_length**2 / excess
        vertical_tension = submerged_weight_mn_per_m * line_length_m
        return horizontal_tension, math.hypot(horizontal_tension, vertical_tension)

    suspended_span = math.sqrt(max(line_length_m**2 - fairlead_height_m**2, 1e-6))

    def span_from_a(a: float) -> float:
        return 2.0 * a * math.sinh(horizontal_span_m / (2.0 * a))

    low = 1e-3
    high = 1.0
    while span_from_a(high) > suspended_span and high < 1e8:
        high *= 2.0

    for _ in range(24):
        mid = 0.5 * (low + high)
        if span_from_a(mid) > suspended_span:
            low = mid
        else:
            high = mid

    a = high
    horizontal_tension = submerged_weight_mn_per_m * a
    vertical_tension = submerged_weight_mn_per_m * line_length_m
    return horizontal_tension, math.hypot(horizontal_tension, vertical_tension)


def _catenary_offset_for_chain(
    chain: dict,
    environmental_force_mn: float,
    line_count: int,
    water_depth_m: float,
    draft_m: float,
    column_spacing_m: float,
    allowable_offset_m: float,
    safety_factor: float,
) -> dict:
    fairlead_height = max(1.0, water_depth_m - draft_m)
    anchor_radius = max(3.0 * water_depth_m, 2.0 * column_spacing_m)
    line_length = 1.02 * math.hypot(anchor_radius, fairlead_height)
    submerged_weight = chain["mass_t_per_m"] * G / 1000.0 * (1.0 - RHO_SEAWATER_T_PER_M3 / STEEL_DENSITY_T_PER_M3)

    h0, t0 = _catenary_horizontal_tension(submerged_weight, line_length, anchor_radius, fairlead_height)
    target_restoring = environmental_force_mn * safety_factor

    def restoring_at(offset: float) -> tuple[float, float, float]:
        h, t = _catenary_horizontal_tension(
            submerged_weight,
            line_length,
            anchor_radius + max(0.0, offset),
            fairlead_height,
        )
        restoring = line_count * max(0.0, h - h0)
        return restoring, h, t

    restoring_limit, _, _ = restoring_at(allowable_offset_m)
    if restoring_limit <= 1e-9:
        offset = max(allowable_offset_m * 4.0, water_depth_m * 0.25, 20.0)
    else:
        offset = allowable_offset_m * target_restoring / restoring_limit
    restoring, h, fairlead_tension = restoring_at(offset)

    equivalent_stiffness = environmental_force_mn / max(offset, 1e-6)
    pretension_t = t0 * 1000.0 / G
    return {
        "offset_m": offset,
        "equivalent_stiffness_mn_per_m": equivalent_stiffness,
        "line_length_m": line_length,
        "pretension_t": pretension_t,
        "fairlead_tension_mn": fairlead_tension,
        "restoring_mn": restoring,
    }


def _mooring_screen(
    inputs: DesignInputs,
    column_diameter_m: float,
    column_spacing_m: float,
    draft_m: float,
) -> dict:
    """Quasi-static catenary mooring and offset screening."""
    line_count = max(3, int(inputs.mooring_line_count))
    allowable_offset = max(1.0, inputs.water_depth_m * inputs.allowable_offset_pct_depth / 100.0)

    projected_area = max(1.0, 3.0 * column_diameter_m * draft_m)
    wave_drift = 0.00008 * projected_area * inputs.hs_m**2
    environmental_force = inputs.max_thrust_mn + wave_drift
    required_stiffness = environmental_force * inputs.mooring_safety_factor / allowable_offset

    selected_chain = CHAIN_LIBRARY[-1]
    selected_response = None
    selected_utilization = math.inf

    for chain in CHAIN_LIBRARY:
        response = _catenary_offset_for_chain(
            chain,
            environmental_force,
            line_count,
            inputs.water_depth_m,
            draft_m,
            column_spacing_m,
            allowable_offset,
            inputs.mooring_safety_factor,
        )
        utilization = response["fairlead_tension_mn"] * inputs.mooring_safety_factor / max(chain["mbl_mn"], 1e-6)
        selected_chain = chain
        selected_response = response
        selected_utilization = utilization
        if response["offset_m"] <= allowable_offset and utilization <= inputs.mooring_utilization_limit:
            break

    assert selected_response is not None
    selected_stiffness = selected_response["equivalent_stiffness_mn_per_m"]
    offset = selected_response["offset_m"]
    offset_pct = 100.0 * offset / max(inputs.water_depth_m, 1e-6)
    line_length = selected_response["line_length_m"]
    mass_per_m_t = selected_chain["mass_t_per_m"]
    mooring_mass = mass_per_m_t * line_length * line_count
    pretension_t = selected_response["pretension_t"]

    anchor_cost_musd = 0.31 * line_count * (selected_chain["diameter_mm"] / 120.0) ** 1.2
    install_cost_musd = 0.10 * line_count * (inputs.water_depth_m / 200.0) ** 0.35
    mooring_cost = (
        mooring_mass * USD_PER_T_CHAIN / 1_000_000.0
        + anchor_cost_musd
        + install_cost_musd
    ) * inputs.mooring_cost_multiplier

    offset_pass = offset <= allowable_offset
    utilization = selected_utilization
    mooring_pass = utilization <= inputs.mooring_utilization_limit and offset_pass

    return {
        "environmental_force_mn": environmental_force,
        "wave_drift_force_mn": wave_drift,
        "allowable_offset_m": allowable_offset,
        "mooring_required_stiffness_mn_per_m": required_stiffness,
        "mooring_stiffness_mn_per_m": selected_stiffness,
        "offset_m": offset,
        "offset_pct_depth": offset_pct,
        "mooring_line_diameter_mm": selected_chain["diameter_mm"],
        "mooring_line_length_m": line_length,
        "mooring_fairlead_tension_mn": selected_response["fairlead_tension_mn"],
        "mooring_pretension_t_per_line": pretension_t,
        "mooring_utilization": utilization,
        "mooring_mass_t": mooring_mass,
        "mooring_cost_musd": mooring_cost,
        "offset_pass": offset_pass,
        "mooring_pass": mooring_pass,
        "mooring_utilization": utilization,
    }


def _capex_breakdown(inputs: DesignInputs, structural_mass_t: float, ballast_t: float, mooring_cost_musd: float) -> dict:
    platform = (structural_mass_t * USD_PER_T_STEEL + max(0.0, ballast_t) * USD_PER_T_BALLAST) / 1_000_000.0
    wtg = inputs.turbine_mw * USD_PER_MW_WTG / 1_000_000.0
    bop = inputs.turbine_mw * USD_PER_MW_ELECTRICAL / 1_000_000.0
    installation = (USD_INSTALL_BASE * (inputs.turbine_mw / 15.0) ** 0.55 * (inputs.water_depth_m / 200.0) ** 0.18) / 1_000_000.0
    foundation_total = platform + mooring_cost_musd + bop + installation
    return {
        "platform_capex_musd": platform,
        "wtg_capex_musd": wtg,
        "foundation_capex_musd": foundation_total,
        "balance_of_plant_musd": bop,
        "installation_capex_musd": installation,
        "total_capex_musd": foundation_total,
        "capex_per_mw_musd": foundation_total / max(inputs.turbine_mw, 1e-6),
    }


def _constraint_margins_from_inputs(inputs: DesignInputs, result: SemiSubResult) -> dict[str, float]:
    ballast_upper = result.ballast_t / max(0.75 * result.buoyancy_t, 1e-6)
    ballast_positive = 0.0 if result.ballast_t > 0 else 1.0 + abs(result.ballast_t) / max(result.buoyancy_t, 1.0)
    return {
        "column diameter": result.column_diameter_m / max(inputs.max_column_diameter_m, 1e-6),
        "GM": inputs.gm_min_m / max(result.gm_m, 1e-6),
        "pitch / heel": result.static_heel_deg / max(inputs.allowable_pitch_deg, 1e-6),
        "port draft": result.draft_m / max(inputs.port_draft_limit_m, 1e-6),
        "ballast positive": ballast_positive,
        "ballast fraction": ballast_upper,
        "offset": result.offset_m / max(result.allowable_offset_m, 1e-6),
        "mooring strength": result.mooring_utilization / max(inputs.mooring_utilization_limit, 1e-6),
    }


def most_restrictive_constraint(inputs: DesignInputs, result: SemiSubResult) -> tuple[str, float]:
    margins = _constraint_margins_from_inputs(inputs, result)
    failed = {name: margin for name, margin in margins.items() if margin > 1.0}
    if not failed:
        return ("none", 1.0)
    return max(failed.items(), key=lambda item: item[1])


def evaluate_semisub(inputs: DesignInputs, template: SemiSubTemplate | None = None) -> SemiSubResult:
    template = template or SemiSubTemplate()

    # Scaling: use rotor diameter for length scale and thrust for stability scale.
    length_scale = inputs.rotor_diameter_m / template.ref_rotor_diameter_m
    thrust_scale = max(0.85, (inputs.max_thrust_mn / 2.5) ** 0.25)  # soft correction
    s = max(0.65, min(1.45, 0.75 * length_scale + 0.25 * thrust_scale))

    feasible_best = None
    diagnostic_best = None
    freeboard = max(2.0, (template.column_height_m - template.draft_m) * s)
    base_col_dia = template.column_diameter_m * s
    base_spacing = template.column_spacing_m * s
    base_draft = template.draft_m * s
    base_pont_w = template.pontoon_width_m * s
    base_pont_h = template.pontoon_height_m * s

    col_dia_values = sorted({
        round(max(5.0, base_col_dia * m), 3)
        for m in [0.75, 0.85, 0.95, 1.05, 1.15, 1.30, 1.45]
    })
    spacing_values = sorted({
        round(max(35.0, base_spacing * m), 3)
        for m in [0.75, 0.90, 1.00, 1.15, 1.30, 1.50, 1.70, 1.90]
    })
    if inputs.target_draft_m is not None:
        draft_values = [inputs.target_draft_m]
    else:
        draft_values = sorted({
            round(max(8.0, base_draft * m), 3)
            for m in [0.65, 0.75, 0.85, 0.95, 1.05, 1.15, 1.30, 1.45]
        })
    pont_w_values = sorted({
        round(max(5.0, base_pont_w * m), 3)
        for m in [0.75, 0.90, 1.05, 1.20, 1.40]
    })
    pont_h_values = sorted({
        round(max(4.0, base_pont_h * m), 3)
        for m in [0.75, 0.90, 1.05, 1.20, 1.40]
    })

    # Minimize CAPEX over explicit geometry variables:
    # column spacing, column diameter, draft, pontoon width, and pontoon height.
    for col_dia in col_dia_values:
        for spacing in spacing_values:
            for draft in draft_values:
                for pont_w in pont_w_values:
                    for pont_h in pont_h_values:
                        col_height = draft + freeboard
                        structural_mass = _structural_mass_from_geometry(
                            template,
                            col_dia,
                            spacing,
                            col_height,
                            pont_w,
                            pont_h,
                        )

                        col_vol, pont_vol = _component_volumes(template.n_columns, col_dia, spacing, pont_w, pont_h, draft)
                        total_vol = col_vol + pont_vol
                        buoyancy_t = total_vol * RHO_SEAWATER_T_PER_M3
                        lightship_t = structural_mass + inputs.wtg_mass_t
                        ballast_t = buoyancy_t - lightship_t
                        total_mass_t = lightship_t + max(0.0, ballast_t)

                        # Buoyancy centre: pontoons at pont_h/2, columns at draft/2
                        kb = (col_vol * (draft / 2.0) + pont_vol * (pont_h / 2.0)) / max(total_vol, 1e-6)
                        iwp = _waterplane_inertia(template.n_columns, col_dia, spacing)
                        bm = iwp / max(total_vol, 1e-6)

                        # Mass centre: structural, WTG, ballast. Ballast assumed low in pontoon region.
                        structural_cog = min(0.45 * col_height, draft * 0.80)
                        ballast_cog = pont_h * 0.45
                        kg_num = structural_mass * structural_cog + inputs.wtg_mass_t * inputs.wtg_cog_above_keel_m + max(0.0, ballast_t) * ballast_cog
                        kg = kg_num / max(total_mass_t, 1e-6)
                        gm = kb + bm - kg

                        lever = max(1.0, inputs.hub_height_above_keel_m - kb)
                        heeling = inputs.max_thrust_mn * lever
                        theta = math.radians(inputs.allowable_pitch_deg)
                        restoring = (buoyancy_t * G / 1000.0) * gm * math.sin(theta) if gm > 0 else -1.0
                        ratio = restoring / heeling if heeling > 0 else 0.0
                        heel_rad = heeling / max((buoyancy_t * G / 1000.0) * gm, 1e-9) if gm > 0 else math.inf
                        static_heel = math.degrees(heel_rad) if heel_rad < 10 else 999.0

                        gm_pass = gm >= inputs.gm_min_m
                        stability_pass = static_heel <= inputs.allowable_pitch_deg
                        port_pass = draft <= inputs.port_draft_limit_m
                        ballast_pass = ballast_t > 0 and ballast_t < 0.75 * buoyancy_t
                        column_diameter_pass = col_dia <= inputs.max_column_diameter_m
                        mooring = _mooring_screen(inputs, col_dia, spacing, draft)
                        offset_pass = mooring["offset_pass"]
                        mooring_pass = mooring["mooring_pass"]
                        capex = _capex_breakdown(inputs, structural_mass, ballast_t, mooring["mooring_cost_musd"])
                        overall = gm_pass and stability_pass and port_pass and ballast_pass and column_diameter_pass and offset_pass and mooring_pass
                        result = SemiSubResult(
                            template=template.name,
                            turbine_mw=inputs.turbine_mw,
                            allowable_pitch_deg=inputs.allowable_pitch_deg,
                            allowable_offset_pct_depth=inputs.allowable_offset_pct_depth,
                            column_diameter_m=col_dia,
                            column_spacing_m=spacing,
                            column_height_m=col_height,
                            pontoon_width_m=pont_w,
                            pontoon_height_m=pont_h,
                            draft_m=draft,
                            structural_mass_t=structural_mass,
                            displacement_t=buoyancy_t,
                            buoyancy_t=buoyancy_t,
                            ballast_t=ballast_t,
                            total_mass_t=total_mass_t,
                            kb_m=kb,
                            bm_m=bm,
                            kg_m=kg,
                            gm_m=gm,
                            heeling_moment_mnm=heeling,
                            restoring_moment_mnm=restoring,
                            restoring_ratio=ratio,
                            static_heel_deg=static_heel,
                            environmental_force_mn=mooring["environmental_force_mn"],
                            wave_drift_force_mn=mooring["wave_drift_force_mn"],
                            allowable_offset_m=mooring["allowable_offset_m"],
                            mooring_required_stiffness_mn_per_m=mooring["mooring_required_stiffness_mn_per_m"],
                            mooring_stiffness_mn_per_m=mooring["mooring_stiffness_mn_per_m"],
                            offset_m=mooring["offset_m"],
                            offset_pct_depth=mooring["offset_pct_depth"],
                            mooring_line_diameter_mm=mooring["mooring_line_diameter_mm"],
                            mooring_line_length_m=mooring["mooring_line_length_m"],
                            mooring_fairlead_tension_mn=mooring["mooring_fairlead_tension_mn"],
                            mooring_pretension_t_per_line=mooring["mooring_pretension_t_per_line"],
                            mooring_utilization=mooring["mooring_utilization"],
                            mooring_mass_t=mooring["mooring_mass_t"],
                            mooring_cost_musd=mooring["mooring_cost_musd"],
                            platform_capex_musd=capex["platform_capex_musd"],
                            wtg_capex_musd=capex["wtg_capex_musd"],
                            foundation_capex_musd=capex["foundation_capex_musd"],
                            balance_of_plant_musd=capex["balance_of_plant_musd"],
                            installation_capex_musd=capex["installation_capex_musd"],
                            total_capex_musd=capex["total_capex_musd"],
                            capex_per_mw_musd=capex["capex_per_mw_musd"],
                            gm_pass=gm_pass,
                            stability_pass=stability_pass,
                            port_pass=port_pass,
                            ballast_pass=ballast_pass,
                            column_diameter_pass=column_diameter_pass,
                            offset_pass=offset_pass,
                            mooring_pass=mooring_pass,
                            overall_pass=overall,
                            notes="Concept-level estimate. Geometry and mooring are generated from generic semi-sub and catenary-screening correlations.",
                        )
                        if overall:
                            if feasible_best is None or result.total_capex_musd < feasible_best.total_capex_musd:
                                feasible_best = result
                        else:
                            margins = _constraint_margins_from_inputs(inputs, result)
                            violation = sum(max(0.0, margin - 1.0) ** 2 for margin in margins.values())
                            diagnostic_key = (violation, result.total_capex_musd)
                            if diagnostic_best is None or diagnostic_key < diagnostic_best[0]:
                                diagnostic_best = (diagnostic_key, result)

    if feasible_best is not None:
        return feasible_best
    return diagnostic_best[1]


def optimize_capex(
    base_inputs: DesignInputs,
    optimize_wtg: bool = True,
    optimize_draft: bool = True,
    optimize_pitch: bool = True,
    optimize_offset: bool = True,
) -> SemiSubResult:
    turbine_values = [8.0, 10.0, 12.0, 15.0, 18.0, 20.0] if optimize_wtg else [base_inputs.turbine_mw]
    draft_values = [None] if optimize_draft else [base_inputs.target_draft_m]
    if optimize_draft:
        draft_values = [14.0, 16.0, 18.0, 20.0, 22.0, 25.0, 28.0]
    pitch_values = [5.0, 6.0, 7.0, 8.0, 10.0] if optimize_pitch else [base_inputs.allowable_pitch_deg]
    offset_values = [3.0, 4.0, 5.0, 6.0, 8.0] if optimize_offset else [base_inputs.allowable_offset_pct_depth]

    feasible_best = None
    diagnostic_best = None
    for mw in turbine_values:
        turbine = turbine_from_capacity(mw)
        for draft in draft_values:
            for pitch in pitch_values:
                for offset in offset_values:
                    candidate_inputs = replace(
                        base_inputs,
                        turbine_mw=mw,
                        rotor_diameter_m=turbine["rotor_diameter_m"],
                        hub_height_above_keel_m=turbine["hub_height_m"],
                        wtg_mass_t=turbine["mass_t"],
                        wtg_cog_above_keel_m=turbine["cog_m"],
                        max_thrust_mn=turbine["thrust_mn"],
                        target_draft_m=draft,
                        allowable_pitch_deg=pitch,
                        allowable_offset_pct_depth=offset,
                    )
                    result = evaluate_semisub(candidate_inputs)
                    if result.overall_pass:
                        if feasible_best is None or result.total_capex_musd < feasible_best.total_capex_musd:
                            feasible_best = result
                    else:
                        margins = _constraint_margins_from_inputs(candidate_inputs, result)
                        violation = sum(max(0.0, margin - 1.0) ** 2 for margin in margins.values())
                        diagnostic_key = (violation, result.total_capex_musd)
                        if diagnostic_best is None or diagnostic_key < diagnostic_best[0]:
                            diagnostic_best = (diagnostic_key, result)
    if feasible_best is not None:
        return feasible_best
    return diagnostic_best[1]


def result_as_dict(result: SemiSubResult) -> dict:
    d = asdict(result)
    for k, v in list(d.items()):
        if isinstance(v, float):
            d[k] = round(v, 3)
    return d
