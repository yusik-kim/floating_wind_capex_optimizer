# Floating Wind CAPEX Optimizer - Methodology Report

## 1. Purpose and Scope

This report explains the engineering methods implemented in the current Floating Wind Foundation CAPEX Optimizer. The tool is intended for early concept screening of a semi-submersible floating wind platform anchored to the published UMaine VolturnUS-S 15 MW reference design. It estimates platform geometry, displacement, ballast, static stability, mooring offset, mooring cost, and foundation CAPEX.

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
| `allowable_pitch_deg` | Allowable static pitch / heel angle |
| `allowable_offset_pct_depth` | Allowable horizontal offset. The UI presents this in meters and converts it internally to percent of water depth |
| `water_depth_m` | Site water depth |
| `harbor_draft_limit_m` | Maximum allowable harbor draft in the deballasted tow-out condition |
| `max_column_diameter_m` | Maximum allowed column diameter, default 15 m |
| `mooring_utilization_limit` | Maximum allowable mooring strength utilization, default 0.45 |

In the app, the sidebar is intentionally ordered as:

```text
Constraint -> Turbine -> Site
```

The constraint values are fixed project inputs shown as editable numeric fields. Users can still change them to test sensitivity, but the optimizer treats them as constraints rather than design variables.

The current implementation also uses internal default assumptions for hidden advanced parameters:

| Internal assumption | Default |
| --- | ---: |
| `tp_s` | 12 s |
| `mooring_line_count` | 3 |
| `mooring_safety_factor` | 1.5 |
| `mooring_cost_multiplier` | 1.0 |

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

The calculation starts from the UMaine VolturnUS-S platform defined in NREL/TP-5000-76773:

| Parameter | Reference value |
| --- | ---: |
| Reference turbine | 15 MW |
| Reference rotor diameter | 240 m |
| Radial columns | 3 |
| Radial column diameter | 12.5 m |
| Central tower-support column | 1 |
| Central column diameter | 10.0 m |
| Radial column spacing from tower axis | 51.75 m |
| Column height | 35 m |
| Bottom pontoon width | 12.5 m |
| Bottom pontoon height | 7.0 m |
| Upper radial strut diameter | 0.91 m |
| Operation draft | 20 m |
| Freeboard | 15 m |
| Hull displacement | 20,206 m3 |
| Hull steel mass | 3,914 t |
| Fixed ballast mass | 2,540 t |
| Fluid ballast mass | 11,300 t |
| Tower interface mass | 100 t |
| Total platform mass | 17,854 t |

The platform is represented as:

- three radial buoyancy columns
- one central tower-support column
- three rectangular bottom pontoons connecting the center to the radial columns
- three upper radial struts included in the structural mass proxy
- fixed ballast at the base of the radial columns
- seawater ballast in the bottom pontoons

The WTG tower is installed on the central column. The reference values above are reproduced in the app for traceability. Candidate geometries are scaled around this baseline and remain concept-level approximations.

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

The optimizer now varies explicit foundation design variables rather than a single geometry multiplier. The design variables are:

```text
column_spacing
column_diameter
operation_draft
pontoon_width
pontoon_height
```

The turbine-based scale `s` is used only to define a reasonable search center around the 15 MW reference template:

```text
base_column_diameter = reference_column_diameter * s
base_column_spacing  = reference_column_spacing  * s
base_operation_draft = reference_operation_draft * s
base_pontoon_width   = reference_pontoon_width   * s
base_pontoon_height  = reference_pontoon_height  * s
```

The search then explores discrete candidate values around those base dimensions. For example:

```text
column_diameter = base_column_diameter * diameter_multiplier
column_spacing  = base_column_spacing  * spacing_multiplier
operation_draft = base_operation_draft * draft_multiplier
pontoon_width   = base_pontoon_width   * pontoon_width_multiplier
pontoon_height  = base_pontoon_height  * pontoon_height_multiplier
```

Column total height is set from operation draft plus a fixed scaled freeboard:

```text
freeboard = max(2.0, (reference_column_height - reference_operation_draft) * s)
column_height = operation_draft + freeboard
```

This means reducing operation draft also reduces total column height and steel cost. The dry column above still exists for freeboard, but it does not grow artificially when operation draft is reduced.

## 7. Structural Mass Estimate

Structural mass is estimated from a geometry proxy based on the radial-column shells, central-column shell, pontoon member size, and upper struts.

```text
reference_proxy =
    3 * pi * reference_outer_diameter * reference_column_height
    + pi * reference_central_diameter * reference_column_height
    + 3 * reference_spacing
        * 2 * (reference_pontoon_width + reference_pontoon_height)
    + 3 * pi * reference_strut_diameter * reference_spacing
```

```text
candidate_proxy =
    3 * pi * outer_diameter * column_height
    + pi * central_diameter * column_height
    + 3 * radial_spacing * 2 * (pontoon_width + pontoon_height)
    + 3 * pi * strut_diameter * radial_spacing
```

```text
structural_mass =
    3914 t
    * (candidate_proxy / reference_proxy)^1.08
```

Interpretation:

- larger column diameter and height increase column steel
- larger column spacing increases pontoon length
- larger pontoon width and height increase pontoon steel
- the exponent `1.08` adds a mild allowance for larger member sizes and outfitting

This is a concept estimate only. It does not include scantlings, fatigue reinforcement, local buckling, fabrication details, or detailed secondary steel.

## 8. Displacement and Buoyancy

### 8.1 Column Volume

The three radial columns and one central column are modeled as vertical cylinders:

```text
radial_column_volume =
    3 * pi * (outer_diameter / 2)^2 * operation_draft

central_column_volume =
    pi * (central_diameter / 2)^2 * operation_draft
```

The central-column diameter retains the VolturnUS-S diameter ratio:

```text
central_diameter = outer_diameter * (10.0 / 12.5)
```

### 8.2 Pontoon Volume and Reference Calibration

Using full centerline lengths for all three rectangular pontoons would double-count the column-pontoon intersections. The app therefore calibrates an effective pontoon factor to the published `20,206 m3` reference displacement:

```text
f_pontoon =
    (20206 - reference_radial_column_volume
           - reference_central_column_volume)
    / (3 * 51.75 * 12.5 * 7.0)

f_pontoon = 0.829784
```

For a candidate:

```text
pontoon_volume =
    3 * radial_spacing * pontoon_width
    * min(operation_draft, pontoon_height)
    * f_pontoon
```

This makes the reference geometry reproduce the published displacement exactly while avoiding the original centerline-box double counting.

### 8.3 Total Displaced Volume

```text
total_volume =
    radial_column_volume
    + central_column_volume
    + pontoon_volume
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

## 9. Lightship, Fixed Ballast, Fluid Ballast, and Total Mass

VolturnUS-S has two distinct ballast types. Fixed iron-ore-concrete ballast remains at the base of the three radial columns. Fluid seawater ballast is carried in the bottom pontoons and can be removed for harbor operations.

The unballasted mass before either ballast component is:

```text
unballasted_mass_t =
    structural_mass_t
    + tower_interface_mass_t
    + wtg_mass_t
```

Required total ballast follows hydrostatic equilibrium:

```text
required_ballast_t =
    buoyancy_t
    - unballasted_mass_t
    - operational_mooring_vertical_load_equivalent_t
```

The reference report gives a downward mooring vertical load and rounded mass properties. To make the published `20,206 m3` displacement and `17,854 t` platform mass close exactly at the reference point, the app derives the reference equivalent load from the published balance:

```text
reference_mooring_vertical_load_equivalent_t =
    20206 * 1.025
    - 17854
    - 2254

reference_mooring_vertical_load_equivalent_t = 603.15 t
```

For scaled candidates this reference load is scaled with characteristic area. It is included only in the operational vertical force balance; it is removed in the unmoored harbor/tow condition. NREL/TP-5000-76773 separately reports `6,065 kN` mooring vertical pretension; the small difference is consistent with rounded published displacement and component masses.

The fixed ballast target is scaled from the `2,540 t` reference value with candidate displaced volume. Fluid ballast supplies the remaining requirement:

```text
fixed_ballast_t =
    min(scaled_fixed_ballast_target, max(0, required_ballast_t))

fluid_ballast_t =
    required_ballast_t - fixed_ballast_t

total_ballast_t = fixed_ballast_t + fluid_ballast_t
```

Fluid ballast volume and pontoon fill fraction are:

```text
fluid_ballast_volume =
    max(0, fluid_ballast_t) / rho_seawater

fluid_ballast_fill_fraction =
    fluid_ballast_volume / pontoon_volume
```

The ballast check requires:

```text
fluid_ballast_t >= 0
total_ballast_t < 0.75 * buoyancy_t
fluid_ballast_fill_fraction <= 1.0
```

The final condition prevents the optimizer from assigning more seawater ballast than the modeled pontoon volume can contain.

## 9.1 Deballasted Harbor Draft

The optimization draft is the operation draft, i.e. the floating draft with both fixed and fluid ballast included. The harbor draft constraint is checked after removing only the fluid seawater ballast. Fixed ballast remains aboard.

The target deballasted displacement volume is:

```text
harbor_mass_t =
    structural_mass_t
    + tower_interface_mass_t
    + wtg_mass_t
    + fixed_ballast_t

deballasted_volume = harbor_mass_t / rho_seawater
```

The app estimates the deballasted draft from the candidate column and pontoon geometry. If the deballasted waterline is within the pontoon height:

```text
deballasted_draft =
    deballasted_volume
    / (column_waterplane + pontoon_waterplane)
```

where:

```text
column_waterplane =
    3 * pi * (outer_diameter / 2)^2
    + pi * (central_diameter / 2)^2

pontoon_waterplane =
    3 * radial_spacing * pontoon_width * f_pontoon
```

If the pontoons are fully submerged in the deballasted condition:

```text
deballasted_draft =
    pontoon_height
    + (deballasted_volume - pontoon_top_volume)
      / column_waterplane
```

where:

```text
pontoon_top_volume =
    (column_waterplane + pontoon_waterplane) * pontoon_height
```

The harbor draft pass criterion is:

```text
deballasted_draft <= harbor_draft_limit
```

## 10. Center of Buoyancy

The vertical center of buoyancy is estimated by volume-weighted averaging.

For the radial and central columns:

```text
column_KB = operation_draft / 2
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

The three radial-column centers are placed `radial_spacing` from the tower axis at 120-degree intervals. The central column is at the tower axis.

The waterplane second moment about the platform centerline is estimated using the parallel axis theorem:

```text
I_wp =
    sum_over_3_radial_columns(I_outer_local + A_outer * x_i^2)
    + I_central_local
```

The metacentric radius is:

```text
BM = I_wp / total_volume
```

## 12. Center of Gravity

The component CoGs are anchored to the VolturnUS-S mass arrangement:

- structural steel CoG: `12.12 m` above keel at reference scale
- fixed ballast CoG: `1.50 m` above keel
- fluid ballast CoG: `3.15 m` above keel, limited to half the candidate pontoon height
- tower interface CoG: column top
- WTG CoG: turbine table value

The combined center of gravity is:

```text
KG =
    (structural_mass * structural_cog
     + interface_mass * interface_cog
     + wtg_mass * wtg_cog
     + fixed_ballast * fixed_ballast_cog
     + fluid_ballast * fluid_ballast_cog)
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

The ratio is reported as an engineering diagnostic. It is not a separate optimization constraint in the current app; feasibility is governed by the static heel angle, GM, deballasted harbor draft, column diameter, ballast, offset, and mooring utilization constraints.

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

The mooring method is now a quasi-static catenary screening model. It uses a small chain property table, then estimates the fairlead force-offset behavior from catenary equilibrium. This is still a concept-screening model, but the mooring stiffness is no longer prescribed by a fitted `diameter^2` stiffness equation.

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

### 17.2 Mooring Demand

The horizontal load used for mooring screening is:

```text
mooring_demand =
    max_thrust
```

For now, the mooring screening load is rotor thrust only. Current load, wind drag on the platform, second-order hydrodynamic effects, and dynamic amplification are intentionally excluded until a defensible project-specific hydrodynamic method is added.

## 18. Mooring Chain Property Table

The optimizer checks a discrete chain property table, similar in spirit to the WTG table. The current table contains representative offshore chain values:

| Diameter [mm] | Mass [t/m] | MBL [MN] |
| ---: | ---: | ---: |
| 76 | 0.113 | 6.00 |
| 84 | 0.138 | 7.21 |
| 92 | 0.165 | 8.50 |
| 102 | 0.203 | 10.22 |
| 114 | 0.253 | 12.42 |
| 127 | 0.315 | 14.96 |
| 140 | 0.382 | 17.61 |
| 152 | 0.451 | 20.16 |
| 162 | 0.512 | 22.32 |
| 177 | 0.611 | 25.62 |
| 190 | 0.704 | 28.49 |
| 203 | 0.804 | 31.34 |
| 220 | 0.944 | 35.01 |
| 240 | 1.123 | 39.14 |
| 260 | 1.318 | 42.97 |

These values are catalogue-style screening data representative of high-strength offshore mooring chain. They should be replaced by vendor or project chain data before design use. The important change is that mass and MBL are now read from the table rather than calculated from hidden empirical constants.

For each candidate chain, the code evaluates:

```text
diameter
mass_per_m
MBL
```

The lightest chain that satisfies both offset and strength utilization is selected.

## 19. Quasi-Static Catenary Force-Offset Estimate

### 19.1 Layout Assumptions

The current app does not ask the user to define anchor coordinates or line length. Therefore, the model still needs two layout assumptions:

```text
fairlead_height = water_depth - operation_draft
anchor_radius = max(3 * water_depth, 2 * column_spacing)
line_length = 1.02 * sqrt(anchor_radius^2 + fairlead_height^2)
```

These are transparent screening assumptions, not optimized design variables. A project model should replace them with the actual anchor radius, fairlead coordinates, and line length.

### 19.2 Submerged Chain Weight

The chain submerged weight per meter is calculated from the table mass:

```text
submerged_weight =
    mass_per_m * g / 1000 * (1 - rho_water / rho_steel)
```

where:

```text
rho_water = 1.025 t/m^3
rho_steel = 7.85 t/m^3
```

Units:

```text
MN/m = (t/m) * (m/s^2) / 1000
```

### 19.3 Catenary Equation

For an inextensible suspended catenary, the horizontal component of tension is:

```text
H = w * a
```

where:

- `H` is horizontal tension
- `w` is submerged chain weight per meter
- `a` is the catenary parameter

For a line with horizontal span `x`, vertical separation `z`, and length `L`, the catenary parameter is solved numerically from:

```text
sqrt(L^2 - z^2) =
    2 * a * sinh(x / (2 * a))
```

This equation is the standard suspended-catenary relation. The app solves it by bisection.

### 19.4 Offset From Force-Offset Curve

For each chain, the code calculates the initial horizontal fairlead tension at zero offset:

```text
H0 = H(anchor_radius)
```

Then it evaluates the restoring force at the allowable offset:

```text
H_limit = H(anchor_radius + allowable_offset)

restoring_limit =
    line_count * (H_limit - H0)
```

The target restoring force is:

```text
target_restoring =
    mooring_demand * mooring_safety_factor
```

For reporting only, an equivalent required horizontal stiffness is also calculated:

```text
required_stiffness =
    target_restoring / allowable_offset
```

This stiffness is not used to select the line directly. The actual offset check is calculated from the catenary force-offset curve.

The offset is estimated from the secant force-offset slope:

```text
offset =
    allowable_offset * target_restoring / restoring_limit
```

The equivalent stiffness reported in the UI and CSV is then:

```text
equivalent_stiffness =
    mooring_demand / offset
```

This is a fast approximation of the nonlinear force-offset curve, suitable for concept screening. A higher-fidelity model should solve the full multi-line geometry for each offset and include seabed contact, friction, axial stiffness, current, line dynamics, and directional load sharing.

The offset as a percentage of water depth is:

```text
offset_pct_depth = 100 * offset / water_depth
```

The offset pass criterion is:

```text
offset <= allowable_offset
```

## 20. Mooring Mass and Strength Check

Total mooring mass is calculated directly from the selected chain table mass and the calculated line length:

```text
mooring_mass =
    mass_per_m * line_length * line_count
```

Strength utilization is based on catenary fairlead tension at the estimated offset:

```text
utilization =
    fairlead_tension * mooring_safety_factor / MBL
```

The mooring strength pass criterion is:

```text
utilization <= mooring_utilization_limit
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

Foundation CAPEX is:

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

Turbine supply cost is outside the cost model and is not calculated, displayed, exported, or included in the optimization objective. All CAPEX outputs are in million USD.

## 23. Feasibility Constraints

The following Boolean checks are calculated:

```text
gm_pass = GM >= gm_min
```

```text
stability_pass = static_heel_deg <= allowable_pitch_deg
```

```text
port_pass = deballasted_draft <= harbor_draft_limit
```

```text
ballast_pass =
    fluid_ballast >= 0
    and total_ballast < 0.75 * buoyancy
    and fluid_ballast_volume <= pontoon_volume
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
    utilization <= mooring_utilization_limit
    and offset_pass
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

## 24. Feasible Candidate Selection in `evaluate_semisub`

Each geometry candidate is evaluated against the physical constraints first. A candidate is treated as feasible only when:

```text
overall_pass = True
```

Foundation CAPEX is then minimized only among feasible candidates:

```text
minimize foundation_capex
subject to overall_pass = True
```

This means a lower-cost candidate is not allowed to win if it violates GM, pitch, deballasted harbor draft, ballast, column diameter, offset, or mooring constraints.

If no feasible candidate exists in the searched geometry range, the function returns a diagnostic candidate. This fallback is not called a feasible optimum. It is selected by the smallest physical violation margin so the UI can explain which constraint is blocking feasibility.

For a failed candidate, each constraint is converted to a ratio:

```text
constraint_margin = actual_value / allowable_value
```

or, for lower-bound constraints:

```text
constraint_margin = required_value / actual_value
```

A margin below or equal to 1.0 satisfies the constraint. A margin above 1.0 violates it. The largest failed margin is reported as the most restrictive constraint to relax.

## 25. CAPEX Optimization in `optimize_capex`

The top-level optimizer searches foundation design variables:

| Design variable | Role |
| --- | --- |
| Radial column spacing | Hydrostatic restoring and pontoon length |
| Outer column diameter | Buoyancy, waterplane area, and fabrication constraint; central diameter retains the 10/12.5 reference ratio |
| Operation draft | Operating displacement and steel mass |
| Pontoon width | Submerged volume and steel mass |
| Pontoon height | Submerged volume, ballast location, and steel mass |

WTG capacity is selected by the user and is not optimized. The selected WTG capacity is still used to derive rotor diameter, mass, CoG and maximum thrust from the WTG table.

Pitch limit, offset limit, harbor draft limit, GM, column diameter limit, and mooring utilization limit are project constraints. The user can change these constraints with sidebar numeric inputs, but the optimizer does not treat them as design variables. The harbor draft limit is checked against the calculated deballasted draft, not the operation draft.

For each candidate combination:

1. Turbine properties are updated from the WTG table.
2. `evaluate_semisub` generates a platform concept.
3. If the candidate is feasible, it is eligible for CAPEX minimization.
4. If the candidate is infeasible, it is retained only as diagnostic information.

The selected optimized result is:

```text
lowest foundation CAPEX among feasible candidates
```

If no feasible candidate exists in the discrete search range, the UI reports:

```text
No feasible design found.
```

and asks the user to relax the most restrictive physical constraint.

## 26. Interpretation of Results

The optimizer should be interpreted as an early screening tool. It helps answer questions such as:

- How does foundation CAPEX change if the turbine size changes?
- How much does stricter offset limit increase mooring cost?
- Does a harbor draft or column diameter constraint force a larger or more expensive design?
- Is the selected platform concept stable enough under simplified static checks?
- Which physical constraint prevents a feasible design?

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

Several cost and screening-load assumptions should be calibrated against reference projects, vendor data, or higher-fidelity simulations before commercial use. The mooring chain mass and MBL values are now table-based, but the table is still representative screening data rather than project-certified vendor data.

## 28. Recommended Next Improvements

The next technical improvements should be:

1. Add a defensible hydrodynamic/environmental load model for current, platform wind drag, second-order hydrodynamic effects, and dynamic amplification when project data are available.
2. Replace the screening mooring layout assumptions with user-defined anchor coordinates, fairlead coordinates, line length, chain grade, seabed contact, friction, axial stiffness, and directional multi-line load sharing.
3. Add platform motion constraints, especially pitch natural period and pitch response.
4. Add LCOE or revenue-adjusted metrics as alternative objectives, because foundation CAPEX alone does not capture energy production value.
5. Add multiple platform templates: semi-sub, spar, TLP, barge.
6. Add calibration cases from additional public reference platforms.

## 29. References

The platform layout, dimensions, displacement, draft, freeboard, structural mass, fixed ballast, fluid ballast, and tower-interface mass are taken from:

- Allen, C. et al. (2020), *Definition of the UMaine VolturnUS-S Reference Platform Developed for the IEA Wind 15-Megawatt Offshore Reference Wind Turbine*, NREL/TP-5000-76773: https://www.nrel.gov/docs/fy20osti/76773.pdf

The catenary force-offset calculation is based on standard static catenary relations for a flexible line under uniform self-weight:

- Catenary equation and tension relations: https://en.wikipedia.org/wiki/Catenary
- OpenFAST MoorDyn documentation, for context on higher-fidelity mooring modeling beyond this app's quasi-static screen: https://openfast.readthedocs.io/en/main/source/user/moordyn/index.html

For design use, the chain property table should be replaced with project chain data from the applicable standard, supplier catalogue, or certification basis, for example DNV offshore mooring chain requirements or vendor-certified R3/R4/R5 chain data.
