"""
AC configuration — make the pipeline constituency-agnostic.

Each AC has an entry below. To add a new AC, copy the pattern: point at its
booth-list xlsx, demographics CSV, Form-20 xlsx files, and the AC's geographic
center (for the map's default view). Everything else (geocoding, parsing,
heatmap build) is driven by AC_NAME.

Builds are switched with the --ac flag:
    python scripts/build_heatmap.py --ac AC018     # default
    python scripts/build_heatmap.py --ac AC024     # the next constituency
"""

# Each AC: human name, default map center, and source-file basenames.
ACS = {
    "AC018": {
        "name": "Harbour",
        "state": "Tamil Nadu",
        "pc": "Chennai Central",
        "center": (13.092, 80.282),
        "booth_list": "analysis/booth-AC018-2026.xlsx",
        "demographics": "analysis/booth_age_gender_distribution.csv",
        # Form-20 cycles: year -> xlsx path
        "form20": {
            2021: "analysis/AC018-2021.xlsx",
            2024: "analysis/AC018-2024.xlsx",
            2026: "analysis/AC018-2026.xlsx",
        },
        # Output prefix for generated artifacts
        "prefix": "ac018",
        # Geocoding config
        "geocode": {
            "centroid": (13.0921, 80.2822),
            "viewbox": "80.260,13.075,80.300,13.115",
            "user_agent": "ac018-harbour-booth-demographics/1.0",
            "localities": [
                "Sowcarpet", "Kondithope", "Sevenwells", "Seven Wells",
                "Park Town", "George Town", "Muthaiyalpet", "Muthialpet",
                "Vallal Seethakhadhi", "Vallal Seethakathi",
                "Kachaleeswarar", "Kachaleswarar", "Elephantgate", "Elephant Gate",
                "Edapalayam", "Broadway", "Island Ground", "Mannady",
                "Royapuram", "Tondiarpet", "Washermanpet", "Korukkupet",
                "Vannarapettah", "Chintadripet", "Chindadripet",
                "Purasawalkam", "Vepery",
            ],
            "street_overrides": {
                "aremenian street": "Armenian Street",
                "mc leans street": "McLean Street",
                "mclean street": "McLean Street",
                "sevenwells street": "Seven Wells Street",
                "northbeach road": "North Beach Road",
                "north beach road": "North Beach Road",
                "porchuges church street": "Portuguese Church Street",
                "annasalai": "Anna Salai",
                "anna salai": "Anna Salai",
                "v o c salai": "Prakasam Salai",
                "voc salai": "Prakasam Salai",
                "adhiyappan street": "Aadhiyappan Street",
                "aadhiyappa street": "Aadhiyappan Street",
                "ravanaiyar street": "Ravanaiah Street",
                "ek agraharam street": "Ekambaranathar Agraharam Street",
                "ekambaraeswarar agraharam street": "Ekambaranathar Agraharam Street",
            },
            "locality_overrides": {
                "muthaiyalpet": "Muthialpet",
                "muthaialpet": "Muthialpet",
                "muthialpet": "Muthialpet",
                "sevenwells": "Seven Wells Street",
                "seven wells": "Seven Wells Street",
                "vallal seethakhadhi": "Vallal Seethakathi Nagar",
                "vallal seethakathi": "Vallal Seethakathi Nagar",
                "elephantgate": "Elephant Gate",
                "elephant gate": "Elephant Gate",
                "edapalayam": "Edapalayam, Chennai",
                "kachaleeswarar": "Kachaleeswarar Temple, Chennai",
                "kachaleswarar": "Kachaleeswarar Temple, Chennai",
                "island ground": "Island Ground, Chennai",
            },
        },
    },
    "AC019": {
        "name": "Chepauk-Thiruvallikeni",
        "state": "Tamil Nadu",
        "pc": "Chennai Central",
        "center": (13.062, 80.273),
        "booth_list": "../chepauk/analysis/booth-AC019-2026.pdf",
        "demographics": "../chepauk/analysis/booth_age_gender_distribution.csv",
        "form20": {
            2021: "../chepauk/analysis/AC019-2021.pdf",
            2024: "../chepauk/analysis/AC019-2024.pdf",
            2026: "../chepauk/analysis/AC019-2026.pdf",
        },
        "prefix": "ac019",
        "geocode": {
            "centroid": (13.062, 80.273),
            "viewbox": "80.245,13.040,80.295,13.090",
            "user_agent": "ac019-chepauk-booth-demographics/1.0",
            "localities": [
                "Chintadripet", "Chindadripet", "Triplicane",
                "Thiruvallikeni", "Royapettah", "Chepauk",
                "Pudupet", "Pudhupet", "Pudhupakkam",
                "Adikesavapuram", "Adikeshavapuram", "Marina",
                "Anna Salai", "Bharathi Salai", "Peters Road",
                "Thiruvatteeswaranpet", "Thiruvateeswaranpet",
                "Pall Patta", "Pallpatta", "Chetput",
                "Thousand Lights", "West Cott Road",
            ],
            "street_overrides": {},
            "locality_overrides": {
                "chindadripet": "Chintadripet",
                "thiruvallikeni": "Triplicane",
                "pudhupet": "Pudupet",
                "pudhupakkam": "Pudupet",
                "adikeshavapuram": "Adikesavapuram",
                "thiruvatteeswaranpet": "Thiruvatteeswaranpetta",
                "thiruvateeswaranpet": "Thiruvatteeswaranpetta",
                "pallpatta": "Pall Patta",
            },
        },
    },
}

DEFAULT_AC = "AC018"


def get(ac_name=None):
    """Return the config dict for an AC (defaults to DEFAULT_AC)."""
    ac_name = ac_name or DEFAULT_AC
    if ac_name not in ACS:
        raise ValueError(f"Unknown AC '{ac_name}'. Known: {list(ACS)}")
    return ACS[ac_name]
