"""
RC Section Visualizer — Constants
MKS (kgf, ksc, mm) & SI Conversions
"""

# ─── Unit Conversions ────────────────────────────────────────────────────────
KSC_TO_MPA = 0.0980665
MPA_TO_KSC = 10.19716

# ─── Standard Materials ──────────────────────────────────────────────────────
STEEL_GRADES = {
    "SR24": 2400,
    "SD30": 3000,
    "SD40": 4000,
    "SD50": 5000,
    "Custom": None,
}

STEEL_LABELS = {
    "SR24": "Plain bar · TIS 20  SR24",
    "SD30": "Deformed · TIS 24  SD30",
    "SD40": "Deformed · TIS 24  SD40",
    "SD50": "Deformed · TIS 24  SD50",
}

CONCRETE_GRADES = {
    "C160": 160,
    "C200": 200,
    "C240": 240,
    "C280": 280,
    "C320": 320,
    "C350": 350,
    "C400": 400,
    "Custom": None,
}

STANDARD_BARS = {
    "DB10": 10,
    "DB12": 12,
    "DB16": 16,
    "DB20": 20,
    "DB25": 25,
    "DB28": 28,
    "DB32": 32,
    "DB36": 36,
}

SECTIONS = {
    "Ext": "Exterior Span",
    "Mid": "Mid Span",
    "Int": "Interior Span",
}
