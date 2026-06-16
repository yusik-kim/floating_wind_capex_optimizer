# Floating Wind CAPEX Optimizer v0.4

Semi-sub template-based prototype implementing modules 1-6:

1. Template platform scaling
2. Weight estimation
3. Hydrostatic analysis
4. Static stability analysis
5. Mooring and offset screening
6. CAPEX optimization with mobile-friendly visual layout

## Run

```bash
pip install -r requirements.txt
py -m streamlit run app.py
```

This is concept-level screening only. It is not suitable for certification or FEED design without independent verification.

Module 5 uses generic catenary mooring correlations to estimate required horizontal stiffness, selected line size, pretension, offset, mooring mass and indicative mooring cost.

Module 6 adds a "Minimize CAPEX" workflow. The user can optimize or manually set four levers:

1. WTG capacity
2. Draft
3. Pitch / heel limit
4. Offset limit

All cost outputs are shown in USD. The app also includes dynamic top-view and side-view platform sketches, and a maximum column diameter constraint set to 12 m by default.
