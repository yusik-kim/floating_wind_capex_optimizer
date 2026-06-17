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

Module 5 uses generic catenary mooring correlations to estimate required horizontal stiffness, selected line size, pretension, offset, mooring mass and indicative mooring cost.

Module 6 adds a "Minimize Foundation CAPEX" workflow. WTG capacity remains a user-selected sizing input, and WTG mass, CoG and thrust are taken from the built-in WTG table. WTG supply cost is shown separately but excluded from the optimization objective.

The user can optimize or manually set three foundation design levers:

1. Draft
2. Pitch / heel limit
3. Offset limit

All cost outputs are shown in USD. The app also includes dynamic top-view and side-view foundation sketches, and a maximum column diameter constraint set to 12 m by default.
