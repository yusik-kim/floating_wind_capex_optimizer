"""
Floating Wind Concept Optimizer v0.4
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


TURBINE_LIBRARY = [
    {"mw": 8.0, "rotor_diameter_m": 170.0, "hub_height_m": 115.0, "mass_t": 1150.0, "cog_m": 62.0, "thrust_mn": 1.25},
    {"mw": 10.0, "rotor_diameter_m": 190.0, "hub_height_m": 125.0, "mass_t": 1450.0, "cog_m": 68.0, "thrust_mn": 1.55},
    {"mw": 12.0, "rotor_diameter_m": 220.0, "hub_height_m": 138.0, "mass_t": 1800.0, "cog_m": 74.0, "thrust_mn": 2.05},
    {"mw": 15.0, "rotor_diameter_m": 240.0, "hub_height_m": 150.0, "mass_t": 2200.0, "cog_m": 80.0, "thrust_mn": 2.50},
    {"mw": 18.0, "rotor_diameter_m": 270.0, "hub_height_m": 165.0, "mass_t": 2750.0, "cog_m": 90.0, "thrust_mn": 3.15},
    {"mw": 20.0, "rotor_diameter_m": 290.0, "hub_height_m": 175.0, "mass_t": 3200.0, "cog_m": 98.0, "thrust_mn": 3.65},
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
    restoring_ratio_min: float = 1.3
    mooring_line_count: int = 3
    allowable_offset_pct_depth: float = 5.0
    mooring_safety_factor: float = 1.5
    mooring_cost_multiplier: float = 1.0
    max_column_diameter_m: float = 12.0
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
    mooring_pretension_t_per_line: float
    mooring_mass_t: float
    mooring_cost_musd: float
    platform_capex_musd: float
    wtg_capex_musd: float
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
    restoring_ratio_min: float = 1.3,
    mooring_line_count: int = 3,
    allowable_offset_pct_depth: float = 5.0,
    mooring_safety_factor: float = 1.5,
    mooring_cost_multiplier: float = 1.0,
    max_column_diameter_m: float = 12.0,
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
        restoring_ratio_min=restoring_ratio_min,
        mooring_line_count=mooring_line_count,
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


def _waterplane_inertia(n: int, col_dia: float, spacing: float) -> float:
    """Approximate waterplane second moment about platform centreline [m4]."""
    area = math.pi * (col_dia / 2.0) ** 2
    local_i = math.pi * (col_dia / 2.0) ** 4 / 4.0
    radius = spacing / math.sqrt(3.0)
    # column coordinates for triangular layout
    coords = [(radius, 0.0), (-0.5 * radius, math.sqrt(3)/2 * radius), (-0.5 * radius, -math.sqrt(3)/2 * radius)]
    # use inertia about y-axis: sum(I_local + A*x^2)
    return sum(local_i + area * x**2 for x, _ in coords[:n])


def _mooring_screen(
    inputs: DesignInputs,
    column_diameter_m: float,
    column_spacing_m: float,
    draft_m: float,
) -> dict:
    """First-order catenary mooring and offset screening."""
    line_count = max(3, int(inputs.mooring_line_count))
    allowable_offset = max(1.0, inputs.water_depth_m * inputs.allowable_offset_pct_depth / 100.0)

    projected_area = max(1.0, 3.0 * column_diameter_m * draft_m)
    wave_drift = 0.00008 * projected_area * inputs.hs_m**2
    environmental_force = inputs.max_thrust_mn + wave_drift
    required_stiffness = environmental_force * inputs.mooring_safety_factor / allowable_offset

    depth_factor = math.sqrt(max(60.0, inputs.water_depth_m) / 200.0)
    spacing_factor = max(0.8, min(1.4, column_spacing_m / 72.0))
    selected_diameter = 220.0
    selected_stiffness = 0.0
    selected_mbl = 0.0

    for diameter in [76, 84, 92, 102, 114, 127, 140, 152, 162, 177, 190, 203, 220]:
        mbl_mn = 0.00055 * diameter**2
        line_stiffness = 0.000018 * diameter**2 / depth_factor
        total_stiffness = line_count * line_stiffness * spacing_factor
        selected_diameter = float(diameter)
        selected_stiffness = total_stiffness
        selected_mbl = mbl_mn
        if total_stiffness >= required_stiffness:
            break

    offset = environmental_force / max(selected_stiffness, 1e-6)
    offset_pct = 100.0 * offset / max(inputs.water_depth_m, 1e-6)
    line_length = inputs.water_depth_m * 3.2 + column_spacing_m
    mass_per_m_t = 0.0000195 * selected_diameter**2
    mooring_mass = mass_per_m_t * line_length * line_count
    pretension_mn = 0.09 * selected_mbl
    pretension_t = pretension_mn * 1000.0 / G

    anchor_cost_musd = 0.31 * line_count * (selected_diameter / 120.0) ** 1.2
    install_cost_musd = 0.10 * line_count * (inputs.water_depth_m / 200.0) ** 0.35
    mooring_cost = (
        mooring_mass * USD_PER_T_CHAIN / 1_000_000.0
        + anchor_cost_musd
        + install_cost_musd
    ) * inputs.mooring_cost_multiplier

    offset_pass = offset <= allowable_offset
    utilization = environmental_force * inputs.mooring_safety_factor / max(line_count * selected_mbl, 1e-6)
    mooring_pass = utilization <= 0.45

    return {
        "environmental_force_mn": environmental_force,
        "wave_drift_force_mn": wave_drift,
        "allowable_offset_m": allowable_offset,
        "mooring_required_stiffness_mn_per_m": required_stiffness,
        "mooring_stiffness_mn_per_m": selected_stiffness,
        "offset_m": offset,
        "offset_pct_depth": offset_pct,
        "mooring_line_diameter_mm": selected_diameter,
        "mooring_line_length_m": line_length,
        "mooring_pretension_t_per_line": pretension_t,
        "mooring_mass_t": mooring_mass,
        "mooring_cost_musd": mooring_cost,
        "offset_pass": offset_pass,
        "mooring_pass": mooring_pass,
    }


def _capex_breakdown(inputs: DesignInputs, structural_mass_t: float, ballast_t: float, mooring_cost_musd: float) -> dict:
    platform = (structural_mass_t * USD_PER_T_STEEL + max(0.0, ballast_t) * USD_PER_T_BALLAST) / 1_000_000.0
    wtg = inputs.turbine_mw * USD_PER_MW_WTG / 1_000_000.0
    bop = inputs.turbine_mw * USD_PER_MW_ELECTRICAL / 1_000_000.0
    installation = (USD_INSTALL_BASE * (inputs.turbine_mw / 15.0) ** 0.55 * (inputs.water_depth_m / 200.0) ** 0.18) / 1_000_000.0
    total = platform + mooring_cost_musd + wtg + bop + installation
    return {
        "platform_capex_musd": platform,
        "wtg_capex_musd": wtg,
        "balance_of_plant_musd": bop,
        "installation_capex_musd": installation,
        "total_capex_musd": total,
        "capex_per_mw_musd": total / max(inputs.turbine_mw, 1e-6),
    }


def evaluate_semisub(inputs: DesignInputs, template: SemiSubTemplate | None = None) -> SemiSubResult:
    template = template or SemiSubTemplate()

    # Scaling: use rotor diameter for length scale and thrust for stability scale.
    length_scale = inputs.rotor_diameter_m / template.ref_rotor_diameter_m
    thrust_scale = max(0.85, (inputs.max_thrust_mn / 2.5) ** 0.25)  # soft correction
    s = max(0.65, min(1.45, 0.75 * length_scale + 0.25 * thrust_scale))

    best = None
    draft_mults = [0.90, 1.00, 1.10, 1.20, 1.30]
    if inputs.target_draft_m is not None:
        draft_mults = [max(0.55, min(1.60, inputs.target_draft_m / max(template.draft_m * s, 1e-6)))]

    # Iterate modestly over additional stability scale and draft to meet constraints.
    for geom_mult in [1.00, 1.05, 1.10, 1.15, 1.20, 1.30, 1.40, 1.55, 1.70, 1.90, 2.10]:
        for draft_mult in draft_mults:
            col_dia = template.column_diameter_m * s * geom_mult
            spacing = template.column_spacing_m * s * geom_mult
            col_height = template.column_height_m * s * max(1.0, draft_mult)
            pont_w = template.pontoon_width_m * s * geom_mult
            pont_h = template.pontoon_height_m * s * min(1.2, draft_mult)
            draft = min(col_height * 0.85, template.draft_m * s * draft_mult)
            structural_mass = template.structural_mass_t * (s ** 2.55) * (geom_mult ** 2.2) * (0.95 + 0.1 * draft_mult)

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
            structural_cog = min(template.structural_cog_above_keel_m * s * draft_mult, draft * 0.75)
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
            stability_pass = ratio >= inputs.restoring_ratio_min and static_heel <= inputs.allowable_pitch_deg
            port_pass = draft <= inputs.port_draft_limit_m
            ballast_pass = ballast_t > 0 and ballast_t < 0.75 * buoyancy_t
            column_diameter_pass = col_dia <= inputs.max_column_diameter_m
            mooring = _mooring_screen(inputs, col_dia, spacing, draft)
            offset_pass = mooring["offset_pass"]
            mooring_pass = mooring["mooring_pass"]
            capex = _capex_breakdown(inputs, structural_mass, ballast_t, mooring["mooring_cost_musd"])
            overall = gm_pass and stability_pass and port_pass and ballast_pass and column_diameter_pass and offset_pass and mooring_pass
            score = capex["total_capex_musd"]
            if not gm_pass:
                score += 100000 * (inputs.gm_min_m - gm)
            if not stability_pass:
                score += 100000 * max(0.0, inputs.restoring_ratio_min - ratio)
                score += 10000 * max(0.0, static_heel - inputs.allowable_pitch_deg)
            if not port_pass:
                score += 100000 * (draft - inputs.port_draft_limit_m)
            if not column_diameter_pass:
                score += 100000 * (col_dia - inputs.max_column_diameter_m)
            if not ballast_pass:
                if ballast_t <= 0:
                    score += 100000 * (1.0 + abs(ballast_t) / max(buoyancy_t, 1.0))
                else:
                    score += 100000 * max(0.0, ballast_t / max(buoyancy_t, 1.0) - 0.75)
            if not offset_pass:
                score += 100000 * (mooring["offset_m"] / max(mooring["allowable_offset_m"], 1e-6) - 1.0)
            if not mooring_pass:
                score += 10000
            candidate = (score, SemiSubResult(
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
                mooring_pretension_t_per_line=mooring["mooring_pretension_t_per_line"],
                mooring_mass_t=mooring["mooring_mass_t"],
                mooring_cost_musd=mooring["mooring_cost_musd"],
                platform_capex_musd=capex["platform_capex_musd"],
                wtg_capex_musd=capex["wtg_capex_musd"],
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
                notes="Concept-level estimate. Geometry and mooring are generated from generic semi-sub and catenary-screening correlations."
            ))
            if best is None or candidate[0] < best[0]:
                best = candidate
            if overall:
                return candidate[1]
    return best[1]


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

    best = None
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
                    penalty = 0.0 if result.overall_pass else 1_000_000.0
                    score = result.total_capex_musd + penalty
                    if best is None or score < best[0]:
                        best = (score, result)
    return best[1]


def result_as_dict(result: SemiSubResult) -> dict:
    d = asdict(result)
    for k, v in list(d.items()):
        if isinstance(v, float):
            d[k] = round(v, 3)
    return d
