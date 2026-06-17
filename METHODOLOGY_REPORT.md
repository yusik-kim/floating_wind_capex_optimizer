# Floating Wind CAPEX Optimizer - Methodology Report

## 1. Purpose and Scope

This report explains the engineering methods implemented in the current Floating Wind Foundation CAPEX Optimizer. The tool is intended for early concept screening of a generic three-column semi-submersible floating wind platform. It estimates platform geometry, displacement, ballast, static stability, mooring offset, mooring cost, and foundation CAPEX excluding WTG supply cost.

The methods are concept-level correlations. They are not a replacement for hydrostatic software, coupled time-domain analysis, detailed mooring design, structural design, FEED, class approval, or certification.

The core calculation functions are:

- `turbine_from_capacity`
- `design_inputs_from_turbine`
- `evaluate_semisub`
- `_mooring_screen`
- `_capex_breakdown`
- `optimize_capex`

## 2. Main Inputs

The primary user-controlled variables are:

| Variable | Meaning |
| --- | --- |
| `turbine_mw` | Wind turbine generator rated capacity |
| `target_draft_m` | Target platform draft, if manual draft control is used |
| `allowable_pitch_deg` | Allowable static pitch / heel angle |
| `allowable_offset_pct_depth` | Allowable horizontal offset. The UI presents this in meters and converts it internally to percent of water depth |
| `water_depth_m` | Site water depth |
| `hs_m` | Significant wave height |
| `tp_s` | Peak wave period, currently stored but not yet used in the equations |
| `port_draft_limit_m` | Maximum allowable draft for port / tow-out |
| `max_column_diameter_m` | Maximum allowed column diameter, default 12 m |
| `mooring_line_count` | Number of mooring lines |
| `mooring_safety_factor` | Safety factor used in required horizontal stiffness |
| `mooring_cost_multiplier` | User multiplier for mooring cost sensitivity |

## 3. Turbine Property Interpolation

The function `turbine_from_capacity(turbine_mw)` estimates turbine properties from a reference table. The table includes turbine capacity, rotor diameter, hub height, WTG mass, WTG center of gravity, and maximum rotor thrust.

For a requested turbine size between two table points, the interpolation factor is:

```text
f = (MW - MW_low) / (MW_high - MW_low)
```

Each turbine property is then interpolated linearly:

```text
X = X_low + f * (X_high - X_low)
```

where `X` can be:

```text
rotor_diameter_m
hub_height_m
mass_t
cog_m
thrust_mn
```

This gives the platform model internally consistent turbine inputs without requiring non-expert users to enter mass, thrust, and CoG manually.

## 4. Semi-Submersible Reference Template

The calculation starts from a generic 15 MW three-column semi-submersible template:

| Parameter | Reference value |
| --- | ---: |
| Reference turbine | 15 MW |
| Reference rotor diameter | 240 m |
| Number of columns | 3 |
| Column diameter | 12 m |
| Column spacing | 72 m |
| Column height | 34 m |
| Pontoon width | 10 m |
| Pontoon height | 8 m |
| Draft | 20 m |
| Structural mass | 6500 t |
| Structural CoG above keel | 11 m |

The platform is represented as:

- three vertical circular columns
- three rectangular pontoons forming a triangular ring
- low ballast in the pontoon region

## 5. Platform Scaling in `evaluate_semisub`

### 5.1 Length Scale

The primary geometry scale is based on rotor diameter:

```text
length_scale = rotor_diameter / reference_rotor_diameter
```

### 5.2 Thrust Scale

The thrust correction is:

```text
thrust_scale = max(0.85, (max_thrust / 2.5)^0.25)
```

The exponent `0.25` is intentionally soft. It prevents thrust from over-dominating the geometry scaling at concept stage.

### 5.3 Combined Scale

The final base scale is:

```text
s = clamp(0.75 * length_scale + 0.25 * thrust_scale, 0.65, 1.45)
```

where:

```text
clamp(x, a, b) = max(a, min(b, x))
```

This prevents unrealistically small or large platforms when users select small or large turbines.

## 6. Geometry Candidate Search

The function searches a set of geometry multipliers:

```text
geom_mult = [1.00, 1.05, 1.10, 1.15, 1.20, 1.30, 1.40, 1.55, 1.70, 1.90, 2.10]
```

If draft is optimized, it searches draft multipliers:

```text
draft_mult = [0.90, 1.00, 1.10, 1.20, 1.30]
```

If the user manually sets draft, the code converts the requested draft into an equivalent draft multiplier:

```text
draft_mult = target_draft / (reference_draft * s)
```

and clamps it:

```text
draft_mult = clamp(draft_mult, 0.55, 1.60)
```

For each candidate, the geometry is:

```text
column_diameter = reference_column_diameter * s * geom_mult
column_spacing  = reference_column_spacing  * s * geom_mult
column_height   = reference_column_height   * s * max(1.0, draft_mult)
pontoon_width   = reference_pontoon_width   * s * geom_mult
pontoon_height  = reference_pontoon_height  * s * min(1.2, draft_mult)
```

Draft is limited by column height:

```text
draft = min(0.85 * column_height, reference_draft * s * draft_mult)
```

## 7. Structural Mass Estimate

Structural mass is scaled from the reference platform:

```text
structural_mass =
    reference_structural_mass
    * s^2.55
    * geom_mult^2.2
    * (0.95 + 0.1 * draft_mult)
```

Interpretation:

- `s^2.55` approximates structural scaling between area and volume scaling.
- `geom_mult^2.2` penalizes larger stability geometry.
- `(0.95 + 0.1 * draft_mult)` adds a modest draft-related mass correction.

This is a concept estimate only. It does not include scantlings, fatigue reinforcement, local buckling, fabrication details, or detailed secondary steel.

## 8. Displacement and Buoyancy

### 8.1 Column Volume

Each column is modeled as a vertical cylinder:

```text
column_volume =
    n_columns * pi * (column_diameter / 2)^2 * draft
```

### 8.2 Pontoon Volume

The pontoons are modeled as rectangular volumes:

```text
pontoon_volume =
    n_columns * column_spacing * pontoon_width * pontoon_height
```

### 8.3 Total Displaced Volume

```text
total_volume = column_volume + pontoon_volume
```

### 8.4 Buoyancy / Displacement

Using seawater density:

```text
rho_seawater = 1.025 t/m^3
```

the buoyant displacement is:

```text
buoyancy_t = total_volume * rho_seawater
```

## 9. Lightship, Ballast, and Total Mass

The lightship mass is:

```text
lightship_t = structural_mass_t + wtg_mass_t
```

The required ballast is calculated from hydrostatic equilibrium:

```text
ballast_t = buoyancy_t - lightship_t
```

The total floating mass is:

```text
total_mass_t = lightship_t + max(0, ballast_t)
```

The ballast check is:

```text
ballast_pass = ballast_t > 0 and ballast_t < 0.75 * buoyancy_t
```

This avoids candidates with negative ballast or excessive ballast fraction.

## 10. Center of Buoyancy

The vertical center of buoyancy is estimated by volume-weighted averaging.

For columns:

```text
column_KB = draft / 2
```

For pontoons:

```text
pontoon_KB = pontoon_height / 2
```

The total center of buoyancy is:

```text
KB =
    (column_volume * column_KB + pontoon_volume * pontoon_KB)
    / total_volume
```

## 11. Waterplane Inertia and BM

The waterplane area of each circular column is:

```text
A_col = pi * (column_diameter / 2)^2
```

The local second moment of area of each circular waterplane is:

```text
I_local = pi * (column_diameter / 2)^4 / 4
```

The column centers are placed on a triangular layout. The radius from platform center to each column center is:

```text
r = column_spacing / sqrt(3)
```

The waterplane second moment about the platform centerline is estimated using the parallel axis theorem:

```text
I_wp = sum(I_local + A_col * x_i^2)
```

The metacentric radius is:

```text
BM = I_wp / total_volume
```

## 12. Center of Gravity

The platform structural CoG is scaled but limited so it does not exceed 75% of draft:

```text
structural_cog = min(reference_structural_cog * s * draft_mult, 0.75 * draft)
```

Ballast is assumed low in the pontoon region:

```text
ballast_cog = 0.45 * pontoon_height
```

The combined center of gravity is:

```text
KG =
    (structural_mass * structural_cog
     + wtg_mass * wtg_cog
     + max(0, ballast) * ballast_cog)
    / total_mass
```

## 13. Static Stability

The metacentric height is:

```text
GM = KB + BM - KG
```

The GM pass criterion is:

```text
GM >= gm_min
```

## 14. Heeling Moment

The heeling moment is estimated from maximum rotor thrust and vertical lever arm:

```text
lever = max(1.0, hub_height_above_keel - KB)
```

```text
heeling_moment = max_thrust * lever
```

Units:

- thrust is in MN
- lever is in m
- heeling moment is in MNm

## 15. Restoring Moment

The allowable heel angle is converted to radians:

```text
theta = allowable_pitch_deg * pi / 180
```

The restoring moment at the allowable angle is:

```text
restoring_moment =
    (buoyancy_t * g / 1000) * GM * sin(theta)
```

where:

```text
g = 9.81 m/s^2
```

The factor `/ 1000` converts tonne-force style mass scaling into MN.

The restoring-to-heeling ratio is:

```text
restoring_ratio = restoring_moment / heeling_moment
```

The stability ratio criterion is:

```text
restoring_ratio >= restoring_ratio_min
```

## 16. Static Heel Angle

The static heel angle is estimated by balancing heeling moment against linearized restoring stiffness:

```text
heel_rad =
    heeling_moment
    / ((buoyancy_t * g / 1000) * GM)
```

Then:

```text
static_heel_deg = heel_rad * 180 / pi
```

The pitch / heel pass criterion is:

```text
static_heel_deg <= allowable_pitch_deg
```

## 17. Mooring and Offset Screening in `_mooring_screen`

The mooring method is a first-order catenary screening model. It estimates the line diameter needed to provide sufficient horizontal stiffness and then checks offset and strength.

### 17.1 Allowable Offset

The allowable horizontal offset is a percentage of water depth:

```text
allowable_offset =
    max(1.0, water_depth * allowable_offset_pct_depth / 100)
```

Example:

```text
water_depth = 200 m
allowable_offset_pct_depth = 5%
allowable_offset = 10 m
```

### 17.2 Platform Projected Area

Projected area is estimated from the three columns:

```text
projected_area =
    max(1.0, 3 * column_diameter * draft)
```

### 17.3 Wave Drift Force

Wave drift force is estimated by:

```text
wave_drift_force =
    0.00008 * projected_area * Hs^2
```

Units:

- projected area is in m^2
- Hs is in m
- wave drift force is in MN

This coefficient is empirical and should be calibrated against reference studies.

### 17.4 Total Environmental Force

The horizontal environmental force is:

```text
environmental_force =
    max_thrust + wave_drift_force
```

This currently includes rotor thrust and a simplified wave drift term. Current, wind drag on platform, second-order drift, and dynamic amplification are not included.

### 17.5 Required Horizontal Mooring Stiffness

The required horizontal stiffness is:

```text
required_stiffness =
    environmental_force * mooring_safety_factor / allowable_offset
```

Units:

```text
MN/m = MN / m
```

This is equivalent to requiring:

```text
offset <= allowable_offset
```

after applying the safety factor.

## 18. Mooring Line Sizing

The code checks a discrete set of chain diameters:

```text
diameter = [76, 84, 92, 102, 114, 127, 140, 152, 162, 177, 190, 203, 220] mm
```

For each line diameter, the approximate minimum breaking load is:

```text
MBL = 0.00055 * diameter^2
```

where:

- diameter is in mm
- MBL is in MN

The depth factor is:

```text
depth_factor = sqrt(max(60, water_depth) / 200)
```

The spacing factor is:

```text
spacing_factor = clamp(column_spacing / 72, 0.8, 1.4)
```

The horizontal stiffness per line is:

```text
line_stiffness =
    0.000018 * diameter^2 / depth_factor
```

The total mooring stiffness is:

```text
total_stiffness =
    line_count * line_stiffness * spacing_factor
```

The first diameter satisfying:

```text
total_stiffness >= required_stiffness
```

is selected.

## 19. Offset Estimate

The estimated offset is:

```text
offset = environmental_force / total_stiffness
```

The offset as a percentage of water depth is:

```text
offset_pct_depth = 100 * offset / water_depth
```

The offset pass criterion is:

```text
offset <= allowable_offset
```

## 20. Mooring Pretension, Mass, and Strength Check

The line length is estimated as:

```text
line_length = 3.2 * water_depth + column_spacing
```

The chain mass per meter is estimated as:

```text
mass_per_m = 0.0000195 * diameter^2
```

where:

- diameter is in mm
- mass per meter is in t/m

Total mooring mass is:

```text
mooring_mass =
    mass_per_m * line_length * line_count
```

Pretension is estimated as 9% of MBL:

```text
pretension_MN = 0.09 * MBL
```

and converted to tonnes:

```text
pretension_t = pretension_MN * 1000 / g
```

The strength utilization is:

```text
utilization =
    environmental_force * mooring_safety_factor
    / (line_count * MBL)
```

The mooring strength pass criterion is:

```text
utilization <= 0.45
```

## 21. Mooring Cost

Mooring cost is estimated from chain mass, anchors, and installation:

```text
chain_cost =
    mooring_mass * USD_PER_T_CHAIN / 1,000,000
```

```text
anchor_cost =
    0.31 * line_count * (diameter / 120)^1.2
```

```text
install_cost =
    0.10 * line_count * (water_depth / 200)^0.35
```

The total mooring cost is:

```text
mooring_cost =
    (chain_cost + anchor_cost + install_cost)
    * mooring_cost_multiplier
```

Units are million USD.

## 22. CAPEX Breakdown in `_capex_breakdown`

The platform cost is:

```text
platform_capex =
    (structural_mass * USD_PER_T_STEEL
     + max(0, ballast) * USD_PER_T_BALLAST)
    / 1,000,000
```

WTG supply cost is:

```text
wtg_capex =
    turbine_mw * USD_PER_MW_WTG / 1,000,000
```

Electrical / balance of plant cost is:

```text
bop_capex =
    turbine_mw * USD_PER_MW_ELECTRICAL / 1,000,000
```

Installation cost is:

```text
installation_capex =
    USD_INSTALL_BASE
    * (turbine_mw / 15)^0.55
    * (water_depth / 200)^0.18
    / 1,000,000
```

Foundation CAPEX, excluding WTG supply cost, is:

```text
foundation_capex =
    platform_capex
    + mooring_cost
    + bop_capex
    + installation_capex
```

CAPEX per MW is:

```text
capex_per_mw =
    foundation_capex / turbine_mw
```

WTG supply cost is still calculated for information:

```text
wtg_capex =
    turbine_mw * USD_PER_MW_WTG / 1,000,000
```

but it is not included in the optimization objective. All CAPEX outputs are in million USD.

## 23. Constraint Checks

The following Boolean checks are calculated:

```text
gm_pass = GM >= gm_min
```

```text
stability_pass =
    restoring_ratio >= restoring_ratio_min
    and static_heel_deg <= allowable_pitch_deg
```

```text
port_pass = draft <= port_draft_limit
```

```text
ballast_pass =
    ballast > 0
    and ballast < 0.75 * buoyancy
```

```text
column_diameter_pass =
    column_diameter <= max_column_diameter
```

```text
offset_pass =
    offset <= allowable_offset
```

```text
mooring_pass =
    utilization <= 0.45
```

Overall feasibility is:

```text
overall_pass =
    gm_pass
    and stability_pass
    and port_pass
    and ballast_pass
    and column_diameter_pass
    and offset_pass
    and mooring_pass
```

## 24. Candidate Scoring in `evaluate_semisub`

Each geometry candidate starts with a score equal to foundation CAPEX:

```text
score = foundation_capex
```

Penalty terms are added if constraints fail. For example:

```text
if GM < gm_min:
    score += 100000 * (gm_min - GM)
```

```text
if draft > port_draft_limit:
    score += 100000 * (draft - port_draft_limit)
```

```text
if column_diameter > max_column_diameter:
    score += 100000 * (column_diameter - max_column_diameter)
```

The same idea is used for restoring ratio, static heel, ballast, offset, and mooring strength.

Important implementation note: `evaluate_semisub` returns the first feasible candidate encountered in its ordered search. The search order starts with smaller geometry and lower draft candidates, so the first feasible solution is usually a low-mass / low-cost concept. If no feasible candidate is found, the function returns the lowest-penalty candidate.

## 25. CAPEX Optimization in `optimize_capex`

The top-level optimizer searches four optional design variables:

| Variable | Candidate values |
| --- | --- |
| Draft | 14, 16, 18, 20, 22, 25, 28 m |
| Pitch limit | 5, 6, 7, 8, 10 deg |
| Offset limit | 3, 4, 5, 6, 8% water depth |

WTG capacity is selected by the user and is not optimized. The selected WTG capacity is still used to derive rotor diameter, mass, CoG and maximum thrust from the WTG table.

If a foundation variable is not optimized, the user-selected value is used instead.

For each candidate combination:

1. Turbine properties are updated from the WTG table.
2. `evaluate_semisub` generates a platform concept.
3. A score is assigned:

```text
score = foundation_capex
```

If the concept is infeasible:

```text
score += 1,000,000
```

The lowest score is selected as the optimized result. If at least one feasible candidate exists, the feasible candidate with the lowest foundation CAPEX is selected. If no feasible candidate exists in the discrete search range, the tool returns the lowest-penalty candidate and the UI reports that no feasible design was found.

## 26. Interpretation of Results

The optimizer should be interpreted as an early screening tool. It helps answer questions such as:

- How does foundation CAPEX change if the turbine size changes?
- How much does stricter offset limit increase mooring cost?
- Does a draft or column diameter constraint force a larger or more expensive design?
- Is the selected platform concept stable enough under simplified static checks?
- What is the approximate CAPEX penalty relative to the optimized concept?

## 27. Current Limitations

The current implementation does not include:

- frequency-domain or time-domain motion response
- wave radiation / diffraction
- second-order drift analysis
- current loading
- dynamic mooring tension
- fatigue analysis
- tendon systems for TLP concepts
- spar or barge platform templates
- structural scantling design
- fabrication schedule effects
- installation vessel availability
- regional supply-chain cost databases
- wake, AEP, OPEX, or LCOE

Several coefficients are empirical and should be calibrated against reference projects, vendor data, or higher-fidelity simulations before commercial use.

## 28. Recommended Next Improvements

The next technical improvements should be:

1. Replace the wave drift coefficient with calibrated site- and geometry-dependent equations.
2. Add a real mooring stiffness model for catenary, semi-taut, and taut systems.
3. Add platform motion constraints, especially pitch natural period and pitch response.
4. Add LCOE or revenue-adjusted metrics as alternative objectives, because foundation CAPEX alone does not capture energy production value.
5. Add multiple platform templates: semi-sub, spar, TLP, barge.
6. Add calibration cases from public reference platforms.
