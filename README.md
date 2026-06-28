# Floating Wind Foundation CAPEX Optimizer v0.6

Semi-sub template-based prototype implementing modules 1-6:

1. Template platform scaling
2. Weight estimation
3. Hydrostatic analysis
4. Static stability analysis
5. Mooring and offset screening
6. Foundation CAPEX optimization with mobile-friendly visual layout

## Run

```bash
pip install -r requirements.txt
py -m streamlit run app.py
```

The semi-submersible baseline is the published UMaine VolturnUS-S 15 MW reference platform: three radial columns, one central tower-support column, three bottom pontoons, and three upper struts. The reference geometry, `20 m` operation draft, `15 m` freeboard, `20,206 m3` displacement, `3,914 t` steel mass, `2,540 t` fixed ballast, `11,300 t` fluid ballast, and `100 t` tower interface are from NREL/TP-5000-76773.

This is concept-level screening only. It is not suitable for certification or FEED design without independent verification.

Module 5 uses a chain property table and a quasi-static catenary force-offset screening calculation to estimate selected line size, offset, mooring mass and indicative mooring cost.

Module 6 adds a foundation CAPEX optimization workflow. WTG capacity remains a user-selected sizing input, and WTG mass, CoG and thrust are taken from the built-in WTG table. Turbine supply cost is outside the cost model and is not displayed.

The optimizer varies five foundation design variables:

1. Radial column spacing
2. Outer radial-column diameter; central diameter retains the VolturnUS-S `10/12.5` ratio
3. Operation draft
4. Pontoon width
5. Pontoon height

The sidebar constraints remain fixed project inputs that the user can edit directly:

1. Pitch limit
2. Harbor draft limit, checked against the deballasted draft
3. Offset limit
4. Maximum column diameter
5. Minimum GM
6. Mooring allowable utilization

All cost outputs are shown in USD. The app includes dynamic top-view and side-view sketches showing the central WTG support, radial columns, pontoons, and upper struts. The maximum outer-column diameter constraint is set to 15 m by default.

Reference: [Definition of the UMaine VolturnUS-S Reference Platform](https://www.nrel.gov/docs/fy20osti/76773.pdf).
