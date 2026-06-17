# Floating Wind Foundation CAPEX Optimizer v0.5

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

This is concept-level screening only. It is not suitable for certification or FEED design without independent verification.

Module 5 uses a chain property table and a quasi-static catenary force-offset screening calculation to estimate selected line size, pretension, offset, mooring mass and indicative mooring cost.

Module 6 adds a foundation CAPEX optimization workflow. WTG capacity remains a user-selected sizing input, and WTG mass, CoG and thrust are taken from the built-in WTG table. WTG supply cost is shown separately but excluded from the optimization objective.

The optimizer varies five foundation design variables:

1. Column spacing
2. Column diameter
3. Draft
4. Pontoon width
5. Pontoon height

The sidebar constraints remain fixed project inputs that the user can edit directly:

1. Pitch limit
2. Port draft limit
3. Offset limit
4. Maximum column diameter
5. Minimum GM
6. Mooring allowable utilization

All cost outputs are shown in USD. The app also includes dynamic top-view and side-view foundation sketches, and a maximum column diameter constraint set to 15 m by default.
