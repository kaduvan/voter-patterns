"""
Alliance map and party styling for Tamil Nadu elections.

PARTY->ALLIANCE: groups a bare party name into its electoral front. This is the
meaningful unit in TN (fronts change between cycles). Apply per-cycle since a
party can switch fronts (e.g. AIADMK broke with BJP in 2026).

PARTY_COLORS: display colors for the main parties/alliances (dark-theme-tuned).

This module is the single source of truth for alliance resolution. Both the
Form-20 enrichment and the heatmap builder import ALLIANCES from here.
"""

# ── Alliance definitions per cycle ──────────────────────────────────────────
# Key = party name (as it appears in ECI Form-20). Value = alliance label.
# Parties not listed default to their own name; unknowns -> "Independent".

ALLIANCES_2026 = {
    "Dravida Munnetra Kazhagam": "SPA",          # DMK-led Secular Progressive Alliance
    "All India Anna Dravida Munnetra Kazhagam": "AIADMK",  # AIADMK contested alone in 2026
    "Tamilaga Vettri Kazhagam": "TVK",           # Vijay's new party, standalone
    "Naam Tamilar Katchi": "NTK",                # standalone
    "Bahujan Samaj Party": "BSP",
    "Tamizhaga Vaazhvurimai Katchi": "TVK2",  # Velmurugan's party, standalone
    "Independent": "Independent",
}

ALLIANCES_2024 = {
    # 2024 was Lok Sabha — Chennai Central PC. DMK+INC alliance vs BJP+ allies.
    "Dravida Munnetra Kazhagam": "SPA",
    "Bahujan Samaj Party": "SPA",        # BSP was with INDIA bloc in 2024
    "Bharatiya Janata Party": "NDA",
    "Desiya Murpokku Dravida Kazhagam": "NDA",  # DMDK was with NDA in 2024 LS
    "Naam Tamilar Katchi": "NTK",
    "Independent": "Independent",
}

ALLIANCES_2021 = {
    "Dravida Munnetra Kazhagam": "SPA",
    "All India Anna Dravida Munnetra Kazhagam": "AIADMK",  # AIADMK+ BJP in 2021, but lead party = AIADMK
    "Bharatiya Janatha Party": "NDA",        # BJP was allied with AIADMK in 2021 (note old spelling 'Janatha')
    "Bharatiya Janata Party": "NDA",    "Paatali Makkal Katchi": "NDA",          # PMK was with AIADMK-BJP in 2021    "Amma Makkal Munnetra Kazhagam": "AMMK",
    "Naam Tamilar Katchi": "NTK",
    "Makkal Neethi Maiam": "MNM",
    "Bahujan Samaj Party": "BSP",
    "Independent": "Independent",
}

ALLIANCES_BY_YEAR = {2021: ALLIANCES_2021, 2024: ALLIANCES_2024, 2026: ALLIANCES_2026}


def alliance_for(party, year):
    """Resolve a party name to its alliance for a given election year."""
    table = ALLIANCES_BY_YEAR.get(year, {})
    if party in table:
        return table[party]
    if not party or party.lower() == "independent":
        return "Independent"
    return party  # unknown party -> show under its own name


# ── Display colors (party + alliance) ───────────────────────────────────────
# Tuned for the dark map background. Saturated enough to read at small sizes.
PARTY_COLORS = {
    "Dravida Munnetra Kazhagam": "#E02020",
    "All India Anna Dravida Munnetra Kazhagam": "#22A84B",
    "Tamilaga Vettri Kazhagam": "#FFB400",       # TVK gold/amber
    "Naam Tamilar Katchi": "#1B7F3F",
    "Bharatiya Janatha Party": "#FF8C00",
    "Bharatiya Janata Party": "#FF8C00",
    "Bahujan Samaj Party": "#1E40D1",
    "Amma Makkal Munnetra Kazhagam": "#0E8C4A",
    "Makkal Neethi Maiam": "#B266FF",
    "Independent": "#7A7A7A",
}

ALLIANCE_COLORS = {
    "SPA": "#E02020",        # DMK-led = red
    "NDA": "#FF8C00",        # BJP-led = saffron
    "AIADMK": "#22A84B",     # green
    "TVK": "#FFB400",        # gold
    "NTK": "#1B7F3F",        # dark green
    "AMMK": "#0E8C4A",
    "MNM": "#B266FF",
    "BSP": "#1E40D1",
    "Independent": "#7A7A7A",
}


def color_for(party_or_alliance, is_alliance=False):
    table = ALLIANCE_COLORS if is_alliance else PARTY_COLORS
    return table.get(party_or_alliance, "#888888")
