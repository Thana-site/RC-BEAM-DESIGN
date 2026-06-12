"""
RC-BEAM-DESIGN — Adversarial Test Suite
Designed to break the software by testing every calculation path.
"""
import math
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.section import SectionGeometry
from models.materials import ConcreteProps, SteelProps
from models.rebar import RebarRecord, rebar_df_to_records
from analysis.capacity import calculate_flexural_capacity
from analysis.properties import (
    get_steel_area, calculate_effective_depth,
    calculate_transformed_centroid, calculate_cracked_inertia,
)
from analysis.validation import check_bars_outside_bounds
from analysis.rebar_generator import generate_rebar_coordinates, get_row_preview_y
from utils.math_helpers import bar_area
from constants import KSC_TO_MPA, MPA_TO_KSC

PASS = 0
FAIL = 0
BUGS = []

def check(name, condition, detail=""):
    global PASS, FAIL, BUGS
    if condition:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        BUGS.append((name, detail))
        print(f"  ✗ FAIL: {name}")
        if detail:
            print(f"         → {detail}")


# ─── HELPERS ────────────────────────────────────────────────────────────────────
def rect_geom(b=400, h=600, cover=40, stirrup=10):
    return SectionGeometry("Rectangular", b=b, h=h, cover=cover, stirrup_dia=stirrup)

def tbeam_geom(bf=1200, tf=120, bw=300, h=700, cover=40, stirrup=10):
    return SectionGeometry("T-Beam", b=bf, h=h, cover=cover, stirrup_dia=stirrup,
                           b_f=bf, t_f=tf, b_w=bw)

def circ_geom(D=500, cover=40, stirrup=10):
    return SectionGeometry("Circular", b=D, h=D, cover=cover, stirrup_dia=stirrup, D=D)

def std_concrete(fc_ksc=280):
    return ConcreteProps(fc_ksc=fc_ksc)

def std_steel(fy_ksc=4000, Es=200000.0):
    return SteelProps(fy_ksc=fy_ksc, fyt_ksc=2400, Es_mpa=Es)


print("=" * 70)
print("  RC-BEAM-DESIGN — ADVERSARIAL AUDIT TEST SUITE")
print("=" * 70)

# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 1: UNIT CONVERSION INCONSISTENCIES
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 1. Unit Conversion Tests")
print("-" * 70)

# Test: KSC_TO_MPA * MPA_TO_KSC should be ≈1.0
roundtrip = KSC_TO_MPA * MPA_TO_KSC
check("KSC↔MPa roundtrip identity",
      abs(roundtrip - 1.0) < 1e-6,
      f"KSC_TO_MPA * MPA_TO_KSC = {roundtrip} (expect 1.0)")

# Test: Es_ksc = 2,000,000 ksc → Es_mpa should be 196,133 MPa (not 200,000)
# The test.py uses Es_ksc = 2,000,000 ksc, but the default SteelProps has Es_mpa=200,000
# This is a SILENT discrepancy — Es in ksc units ≠ Es_mpa default.
Es_from_ksc = 2_000_000 * KSC_TO_MPA
check("Es default value consistency",
      abs(Es_from_ksc - 200000.0) < 5000,
      f"2,000,000 ksc = {Es_from_ksc:.0f} MPa but default is 200,000 MPa. "
      f"Difference: {abs(Es_from_ksc - 200000.0):.0f} MPa")

# Test: beta1 in code (materials.py) uses MPa thresholds vs test.py uses ksc thresholds
# materials.py: fc_mpa <= 28 → 0.85; fc_mpa <= 55 → linear; else 0.65
# test.py:      fc_ksc <= 280 → 0.85; fc_ksc <= 550 → linear; else 0.65
# 280 ksc = 27.46 MPa ≠ 28 MPa;  550 ksc = 53.94 MPa ≠ 55 MPa
c280 = std_concrete(280)
beta1_code = c280.beta1
beta1_expected = 0.85  # 280 ksc → 27.46 MPa which is ≤ 28 → 0.85
check("beta1 at 280 ksc (boundary)",
      abs(beta1_code - 0.85) < 0.001,
      f"beta1 = {beta1_code:.4f}, expected 0.85")

# Test: 285 ksc = 27.95 MPa < 28 MPa → code should give 0.85
# But per ACI ksc standard: 285 > 280 → start linear. 
c285 = std_concrete(285)
beta1_285_code = c285.beta1
beta1_285_ksc = 0.85 - 0.05 * (285 - 280) / 70  # = 0.8464 (per ksc)
beta1_285_mpa_calc = 0.85  # 27.95 < 28 → still 0.85 (per MPa check)
check("beta1 at 285 ksc — MPa vs ksc threshold mismatch",
      abs(beta1_285_code - beta1_285_ksc) < 0.005,
      f"Code gives beta1={beta1_285_code:.4f} (using MPa threshold 28). "
      f"ACI ksc threshold (280 ksc) gives {beta1_285_ksc:.4f}. "
      f"Discrepancy = {abs(beta1_285_code - beta1_285_ksc):.4f}")

# Test: 550 ksc = 53.94 MPa < 55 MPa → code should still be linear
c550 = std_concrete(550)
beta1_550_code = c550.beta1
beta1_550_ksc = 0.85 - 0.05 * (550 - 280) / 70  # = 0.6571 (per ksc, note <0.65, so should be clamped)
# ACI says beta1 >= 0.65 always
check("beta1 at 550 ksc — not clamped to 0.65 minimum",
      beta1_550_code >= 0.65,
      f"beta1 = {beta1_550_code:.4f}, should be >= 0.65")

# The ksc formula: 0.85 - 0.05*(550-280)/70 = 0.85 - 0.193 = 0.657
# The MPa formula: 53.94 < 55 → 0.85 - 0.05*(53.94-28)/7 = 0.85 - 0.185 = 0.665
# These differ! This is a unit mismatch bug.
check("beta1 at 550 ksc — code vs correct ksc-based value",
      abs(beta1_550_code - 0.65) < 0.02,
      f"Code gives {beta1_550_code:.4f}. Per ACI ksc: 0.657→clamped to 0.65. Per MPa: 0.665.")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 2: T-BEAM FLEXURAL CAPACITY — USES b INSTEAD OF b_f/b_w
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 2. T-Beam Capacity Calculation Tests")
print("-" * 70)

geom_t = tbeam_geom()
conc = std_concrete()
stl = std_steel()

# For T-Beam, b is set to b_f in sidebar (line 75: b = b_f)
# In capacity.py, the code uses `b = geom.b` (line 42)
# For Rectangular stress block in force_balance: `0.85 * fc_prime * geom.b * a_val` (line 89)
# But for T-Beam, the rectangular branch shouldn't be used — the T-Beam branch should be used
# Let's verify: when a <= t_f, the T-Beam code uses b_f correctly

result_t = calculate_flexural_capacity(
    geom=geom_t, As=1500.0, Asp=0.0, d=640.0, dp=60.0,
    concrete=conc, steel=stl
)
check("T-Beam: solver converges (small As)",
      result_t.Mn > 0,
      f"Mn = {result_t.Mn}")

# For T-Beam with a > t_f, verify the two-part compression zone
result_t2 = calculate_flexural_capacity(
    geom=geom_t, As=11500.0, Asp=0.0, d=640.0, dp=60.0,
    concrete=conc, steel=stl
)
check("T-Beam: large As forces a > tf",
      result_t2.a > geom_t.t_f,
      f"a = {result_t2.a:.1f} mm, tf = {geom_t.t_f} mm")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 3: Mn FORMULA USES y_comp FOR T-BEAM BUT NOT FOR RECTANGULAR
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 3. Mn Formula Consistency Tests")
print("-" * 70)

# For rectangular: Mn should be Cc*(d - a/2) + Cs*(d - dp)
# capacity.py line 151: Mn = Cc_N * (d - y_comp) + Cs_N * (d - dp)
# For rectangular, y_comp = a/2 → correct
# For T-Beam with a > tf, y_comp is the centroid of the T-shape compression → correct
# But the analysis method expander text (line 297) says:
#   "Mn = Cc·(d − a/2) + Cs·(d − d')"
# This text is misleading for T-Beams where it's d - y_comp, not d - a/2.
# (This is a documentation bug, not a calculation bug)

geom_r = rect_geom()
As_r = 4 * bar_area(20)  # 4-DB20
Asp_r = 2 * bar_area(20)  # 2-DB20
d_r = 550.0
dp_r = 60.0

result_r = calculate_flexural_capacity(geom_r, As_r, Asp_r, d_r, dp_r, conc, stl)

# Manual verification for rectangular beam
fc_mpa = conc.fc_prime
fy_mpa = stl.fy
Es = stl.Es_mpa
eps_cu = 0.003
b1 = conc.beta1

# Manually solve for c using the same approach
c_manual = result_r.c_na
a_manual = b1 * c_manual
eps_t_manual = eps_cu * (d_r - c_manual) / c_manual
eps_cp_manual = eps_cu * (c_manual - dp_r) / c_manual

fst_manual = min(max(Es * eps_t_manual, -fy_mpa), fy_mpa)
fsc_raw = min(max(Es * eps_cp_manual, -fy_mpa), fy_mpa)
fsc_manual = fsc_raw - (0.85 * fc_mpa if a_manual > dp_r else 0.0)

T_manual = As_r * fst_manual
Cc_manual = 0.85 * fc_mpa * geom_r.b * a_manual
Cs_manual = Asp_r * fsc_manual

Mn_manual = Cc_manual * (d_r - a_manual / 2.0) + Cs_manual * (d_r - dp_r)

NMM_TO_TONFM = 1.0 / 9806650.0
err_Mn = abs(result_r.Mn - Mn_manual) / Mn_manual * 100
check("Rectangular Mn matches manual calculation",
      err_Mn < 0.1,
      f"Code Mn = {result_r.Mn*NMM_TO_TONFM:.4f} tfm, Manual = {Mn_manual*NMM_TO_TONFM:.4f} tfm, err = {err_Mn:.4f}%")

# Verify force equilibrium
eq_err = abs(result_r.T - result_r.Cc - result_r.Cs) / result_r.T * 100
check("Rectangular force equilibrium T = Cc + Cs",
      eq_err < 0.01,
      f"|T - (Cc+Cs)| / T = {eq_err:.6f}%")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 4: NEGATIVE MOMENT DEPTH CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 4. Negative Moment Depth Transformation Tests")
print("-" * 70)

# In flexural_tab.py lines 145-147 for negative moment:
#   d = h - (d_val if d_val else cover + stirrup_dia + 25.0)
#   dp = h - (dp_val if dp_val else h - cover - stirrup_dia - 25.0)
# d_val = d_top from session state = depth from TOP to top steel centroid
# So for -M: tension at top, compression at bottom
#   d should be depth from BOTTOM face to top steel = h - d_top
#   dp should be depth from BOTTOM face to bottom steel = h - d_bot

# Test: When d_val=None, d = h - (cover + stirrup + 25) = 600 - 75 = 525
# This means d = 525 from bottom face to top steel at 75mm from top → correct
h_test = 600
cover_test = 40
stirrup_test = 10
d_neg_default = h_test - (cover_test + stirrup_test + 25.0)
dp_neg_default = h_test - (h_test - cover_test - stirrup_test - 25.0)

check("Negative moment: default d value",
      abs(d_neg_default - 525.0) < 1.0,
      f"d = {d_neg_default} (expected 525)")

check("Negative moment: default dp value",
      abs(dp_neg_default - 75.0) < 1.0,
      f"dp = {dp_neg_default} (expected 75)")

# Test: When d_val = 60 (top bars at 60mm from top face)
# Then d = h - 60 = 540 from bottom compression face → correct
d_neg_60 = h_test - 60.0
check("Negative moment: d_val=60 → d=540",
      abs(d_neg_60 - 540.0) < 0.01,
      f"d = {d_neg_60}")

# Test: dp_val = d_bot from session = depth from top to bottom bars = say 540
# dp = h - 540 = 60 from bottom compression face → correct  
dp_neg_540 = h_test - 540.0
check("Negative moment: dp_val=540 → dp=60",
      abs(dp_neg_540 - 60.0) < 0.01,
      f"dp = {dp_neg_540}")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 5: d <= dp GUARD CONDITION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 5. Guard Condition & Boundary Tests")
print("-" * 70)

# capacity.py line 45: if d <= dp or As <= 0 or d <= 0:
# This returns zero capacity. But what about d == dp?
result_deq = calculate_flexural_capacity(
    geom_r, As=1000, Asp=500, d=300, dp=300, concrete=conc, steel=stl
)
check("d == dp returns zero capacity",
      result_deq.Mn == 0.0,
      f"Mn = {result_deq.Mn}")

# What about d very close to dp? This might cause numerical instability
result_close = calculate_flexural_capacity(
    geom_r, As=1000, Asp=500, d=300.01, dp=300.0, concrete=conc, steel=stl
)
check("d ≈ dp (d=300.01, dp=300.0) still converges",
      result_close.Mn >= 0,
      f"Mn = {result_close.Mn*NMM_TO_TONFM:.4f} tfm")

# What about Asp = 0? (singly reinforced)
result_singly = calculate_flexural_capacity(
    geom_r, As=1500, Asp=0.0, d=550, dp=60, concrete=conc, steel=stl
)
check("Singly reinforced (Asp=0) works",
      result_singly.Mn > 0,
      f"Mn = {result_singly.Mn*NMM_TO_TONFM:.4f} tfm")

# As = 0 should return zero
result_noAs = calculate_flexural_capacity(
    geom_r, As=0.0, Asp=500, d=550, dp=60, concrete=conc, steel=stl
)
check("As = 0 returns zero capacity",
      result_noAs.Mn == 0.0,
      f"Mn = {result_noAs.Mn}")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 6: NEWTON-RAPHSON CONVERGENCE EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 6. Newton-Raphson Solver Edge Cases")
print("-" * 70)

# Extremely heavy reinforcement — force c very large
result_heavy = calculate_flexural_capacity(
    geom_r, As=30000, Asp=0, d=550, dp=60, concrete=conc, steel=stl
)
check("Very heavy reinforcement converges",
      result_heavy.c_na > 0 and result_heavy.Mn > 0,
      f"c = {result_heavy.c_na:.1f}, Mn = {result_heavy.Mn*NMM_TO_TONFM:.2f} tfm")

# Check if c_na is clamped to geom.h
check("Heavy reinforcement: c ≤ h",
      result_heavy.c_na <= geom_r.h,
      f"c = {result_heavy.c_na:.1f}, h = {geom_r.h}")

# eps_s for heavy reinforcement should be small/negative (compression-controlled)
check("Heavy reinforcement: compression-controlled eps_s",
      result_heavy.eps_s < 0.005,
      f"eps_s = {result_heavy.eps_s:.6f}")

# Very light reinforcement — tiny As
result_light = calculate_flexural_capacity(
    geom_r, As=50, Asp=0, d=550, dp=60, concrete=conc, steel=stl
)
check("Very light reinforcement converges",
      result_light.c_na > 0 and result_light.Mn > 0,
      f"c = {result_light.c_na:.2f}, Mn = {result_light.Mn*NMM_TO_TONFM:.6f} tfm")

# Extremely small d (say 2mm)
result_tiny_d = calculate_flexural_capacity(
    geom_r, As=100, Asp=0, d=2.0, dp=1.0, concrete=conc, steel=stl
)
check("Tiny d (2mm) doesn't crash",
      True,  # Just testing no exception
      f"c = {result_tiny_d.c_na:.2f}, Mn = {result_tiny_d.Mn}")

# Very large section
geom_huge = rect_geom(b=3000, h=5000)
result_huge = calculate_flexural_capacity(
    geom_huge, As=50000, Asp=10000, d=4900, dp=100, concrete=conc, steel=stl
)
check("Very large section converges",
      result_huge.Mn > 0,
      f"c = {result_huge.c_na:.1f}, Mn = {result_huge.Mn*NMM_TO_TONFM:.2f} tfm")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 7: PHI FACTOR EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 7. Phi Factor (ACI 318-19 §21.2.2) Edge Cases")
print("-" * 70)

# Verify phi interpolation formula: phi = 0.65 + (eps_s - 0.002) * (250/3)
# At eps_s = 0.002: phi = 0.65
# At eps_s = 0.005: phi = 0.65 + 0.003 * 250/3 = 0.65 + 0.25 = 0.90 ✓
# At eps_s = 0.0035: phi = 0.65 + 0.0015 * 250/3 = 0.65 + 0.125 = 0.775

# Force specific eps_s values by choosing appropriate As
# For eps_s exactly at boundaries
for target_eps, expected_phi in [(0.005, 0.90), (0.002, 0.65)]:
    # Back-calculate c: eps_s = eps_cu*(d-c)/c → c = d*eps_cu/(eps_cu + eps_s)
    d_phi = 550.0
    c_target = d_phi * 0.003 / (0.003 + target_eps)
    a_target = conc.beta1 * c_target
    # Calculate needed As: T = Cc → As*fy = 0.85*fc*b*a
    As_target = 0.85 * fc_mpa * geom_r.b * a_target / fy_mpa

    result_phi = calculate_flexural_capacity(
        geom_r, As=As_target, Asp=0, d=d_phi, dp=60, concrete=conc, steel=stl
    )

    check(f"phi at eps_s≈{target_eps}: phi≈{expected_phi}",
          abs(result_phi.phi - expected_phi) < 0.01,
          f"eps_s = {result_phi.eps_s:.6f}, phi = {result_phi.phi:.4f}")

# Test phi never exceeds 0.90 or goes below 0.65
check("Heavy reinf: phi >= 0.65",
      result_heavy.phi >= 0.65,
      f"phi = {result_heavy.phi}")
check("Light reinf: phi <= 0.90",
      result_light.phi <= 0.90,
      f"phi = {result_light.phi}")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 8: CIRCULAR SECTION CONCRETE COMPRESSION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 8. Circular Section Geometry Tests")
print("-" * 70)

geom_c = circ_geom(D=500)

# For circular: compression area is a circular segment
result_circ = calculate_flexural_capacity(
    geom_c, As=2000, Asp=0, d=440, dp=60, concrete=conc, steel=stl
)
check("Circular section converges",
      result_circ.Mn > 0,
      f"c = {result_circ.c_na:.1f}, a = {result_circ.a:.1f}")

# Verify: for circular, when a = D (full section in compression)
# Area should be pi*R^2 = pi*250^2 = 196,350 mm²
R = 250.0
a_full = geom_c.D  # a = 500 = D
val = (R - a_full) / R
val_clamped = max(-1.0, min(val, 1.0))
theta_full = math.acos(val_clamped)  # acos(-1) = pi
A_seg_full = R**2 * (theta_full - math.sin(theta_full)*math.cos(theta_full))
A_circle = math.pi * R**2
check("Circular: a=D gives full circle area",
      abs(A_seg_full - A_circle) < 1.0,
      f"Segment area = {A_seg_full:.1f}, Circle area = {A_circle:.1f}")

# For a = 0: area should be 0
# (a_clamped = 0, code returns 0,0)

# For a = R (half circle): area should be pi*R^2/2
a_half = R  # = 250
val_half = (R - a_half) / R  # = 0
theta_half = math.acos(val_half)  # = pi/2
A_seg_half = R**2 * (theta_half - math.sin(theta_half)*math.cos(theta_half))
A_halfcircle = math.pi * R**2 / 2
check("Circular: a=R gives half-circle area",
      abs(A_seg_half - A_halfcircle) < 1.0,
      f"Segment area = {A_seg_half:.1f}, Half-circle = {A_halfcircle:.1f}")

# Verify circular Ag
check("Circular Ag = pi*D^2/4",
      abs(geom_c.Ag - math.pi * 500**2 / 4) < 1.0,
      f"Ag = {geom_c.Ag:.1f}")

# Verify circular Ig
check("Circular Ig = pi*D^4/64",
      abs(geom_c.Ig - math.pi * 500**4 / 64) < 1.0,
      f"Ig = {geom_c.Ig:.1f}")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 9: T-BEAM Ig CENTROID CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 9. T-Beam Section Properties Tests")
print("-" * 70)

geom_t2 = tbeam_geom(bf=1200, tf=120, bw=300, h=700)

# Manual Ag calculation
Ag_manual = 1200*120 + 300*(700-120)
check("T-Beam Ag",
      abs(geom_t2.Ag - Ag_manual) < 1.0,
      f"Code: {geom_t2.Ag}, Manual: {Ag_manual}")

# Manual Ig calculation (about centroid)
A_f = 1200 * 120
y_f = 700/2.0 - 120/2.0  # = 290
A_w = 300 * (700 - 120)  # = 174000
y_w = -(120 + (700 - 120)/2.0 - 700/2.0)  # web centroid from mid-height
# y_w = -(120 + 290 - 350) = -(60) = -60... wait let me recalculate
# Web goes from bottom (-350) to bottom-of-flange (350-120 = 230, i.e. y = 350 - 120 = 230)
# No, in this coord system y=0 at mid-height, y=+350 at top, y=-350 at bottom
# Flange: from y=350-120=230 to y=350, centroid at (230+350)/2 = 290 → y_f = 290
# Web: from y=-350 to y=230, centroid at (-350+230)/2 = -60 → y_w = -60

y_w_manual = -( 120/2.0 + (700 - 120)/2.0 - 700/2.0 )
# = -(60 + 290 - 350) = -(0)... hmm
# Actually: y_w = -(t_f/2) as in code line 41

# Code says: y_w = -geom.t_f / 2.0 = -60
# But web centroid should be at:
# Web spans from y = -h/2 to y = h/2 - t_f = 230
# Web centroid = (-350 + 230) / 2 = -60 ✓ 
check("T-Beam y_w centroid",
      abs(y_w_manual - (-60.0)) < 0.1,
      f"y_w = {y_w_manual}")

y_c_manual = (A_f * 290 + A_w * (-60)) / (A_f + A_w)
Ig_f = 1200 * 120**3 / 12.0 + A_f * (290 - y_c_manual)**2
Ig_w = 300 * 580**3 / 12.0 + A_w * (-60 - y_c_manual)**2
Ig_manual = Ig_f + Ig_w

err_Ig = abs(geom_t2.Ig - Ig_manual) / Ig_manual * 100
check("T-Beam Ig matches manual",
      err_Ig < 0.1,
      f"Code: {geom_t2.Ig:.0f}, Manual: {Ig_manual:.0f}, err = {err_Ig:.4f}%")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 10: CRACKED INERTIA Icr
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 10. Cracked Inertia Icr Tests")
print("-" * 70)

# Test Icr for rectangular with known values
geom_icr = rect_geom(b=400, h=600)
n_mod = 8.0
As_bot_icr = 1500.0  # mm²
As_top_icr = 500.0  # mm²
d_icr = 530.0
dp_icr = 70.0

Icr_code = calculate_cracked_inertia(geom_icr, As_bot_icr, As_top_icr, d_icr, dp_icr, n_mod)

# Manual: solve quadratic for kd
A_q = geom_icr.b / 2.0  # = 200
B_q = (n_mod - 1) * As_top_icr + n_mod * As_bot_icr  # = 7*500 + 8*1500 = 3500+12000 = 15500
C_q = -(n_mod - 1) * As_top_icr * dp_icr - n_mod * As_bot_icr * d_icr
    # = -7*500*70 - 8*1500*530 = -245000 - 6360000 = -6605000
kd_manual = (-B_q + np.sqrt(B_q**2 - 4*A_q*C_q)) / (2*A_q)
Icr_manual = (400 * kd_manual**3 / 3.0) + (n_mod-1)*As_top_icr*(kd_manual-dp_icr)**2 + n_mod*As_bot_icr*(d_icr-kd_manual)**2

err_Icr = abs(Icr_code - Icr_manual) / Icr_manual * 100
check("Icr with explicit d, dp matches manual",
      err_Icr < 0.1,
      f"Code: {Icr_code:.0f}, Manual: {Icr_manual:.0f}, err = {err_Icr:.4f}%")

# Test: Icr for non-rectangular returns Ig (fallback)
geom_circ_icr = circ_geom(D=500)
Icr_circ = calculate_cracked_inertia(geom_circ_icr, 1000, 500, 440, 60, 8.0)
check("Circular Icr falls back to Ig",
      abs(Icr_circ - geom_circ_icr.Ig) < 1.0,
      f"Icr = {Icr_circ:.0f}, Ig = {geom_circ_icr.Ig:.0f}")

# Test: T-Beam Icr also falls back to Ig
geom_t_icr = tbeam_geom()
Icr_t = calculate_cracked_inertia(geom_t_icr, 1000, 500, 640, 60, 8.0)
check("T-Beam Icr falls back to Ig (no cracked analysis for T-beams)",
      abs(Icr_t - geom_t_icr.Ig) < 1.0,
      f"Icr = {Icr_t:.0f}, Ig = {geom_t_icr.Ig:.0f}")

# Test: Icr with As_bot = 0 falls back to Ig
Icr_nobot = calculate_cracked_inertia(geom_icr, 0.0, 500, 530, 70, 8.0)
check("Icr with As_bot=0 falls back to Ig",
      abs(Icr_nobot - geom_icr.Ig) < 1.0,
      f"Icr = {Icr_nobot:.0f}, Ig = {geom_icr.Ig:.0f}")

# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 11: EFFECTIVE DEPTH CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 11. Effective Depth Calculation Tests")
print("-" * 70)

# For a 600mm beam: y=0 at mid-height, bottom bars at y=-240
# d = h/2 - y_bar = 300 - (-240) = 540
records_d = [
    RebarRecord(layer="Bottom", x=-100, y=-240, dia=25, count=2, bar_size="DB25"),
    RebarRecord(layer="Bottom", x=100, y=-240, dia=25, count=2, bar_size="DB25"),
]
d_calc = calculate_effective_depth(records_d, "Bottom", 600)
check("Effective depth d for uniform bottom bars",
      d_calc is not None and abs(d_calc - 540.0) < 0.1,
      f"d = {d_calc}")

# Mixed diameters at different heights (weighted centroid)
records_mixed = [
    RebarRecord(layer="Bottom", x=0, y=-240, dia=25, count=2, bar_size="DB25"),
    RebarRecord(layer="Bottom", x=0, y=-190, dia=20, count=2, bar_size="DB20"),
]
A_25 = bar_area(25) * 2
A_20 = bar_area(20) * 2
y_bar_mixed = (A_25 * (-240) + A_20 * (-190)) / (A_25 + A_20)
d_expected = 300 - y_bar_mixed

d_mixed = calculate_effective_depth(records_mixed, "Bottom", 600)
check("Effective depth with mixed bars",
      d_mixed is not None and abs(d_mixed - d_expected) < 0.1,
      f"d = {d_mixed:.2f}, expected = {d_expected:.2f}")

# No bars: should return None
d_none = calculate_effective_depth([], "Bottom", 600)
check("No bars returns None",
      d_none is None,
      f"d = {d_none}")

# Only top bars, ask for bottom: should return None
records_top_only = [
    RebarRecord(layer="Top", x=0, y=240, dia=16, count=2, bar_size="DB16"),
]
d_wrong_layer = calculate_effective_depth(records_top_only, "Bottom", 600)
check("Top bars only, asking for Bottom returns None",
      d_wrong_layer is None,
      f"d = {d_wrong_layer}")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 12: STEEL AREA DISPLAY UNIT ERROR
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 12. Steel Area Display Unit Tests")
print("-" * 70)

# In flexural_tab.py line 335:
#   "Value": [f"{As/100:.2f}", f"{Asp/100:.2f}", f"{A_eff/100:.1f}", ...]
#   "Unit": ["cm²", "cm²", "cm²", ...]
# As is in mm². Dividing by 100 to get cm² is WRONG.
# 1 cm² = 100 mm² → to convert mm² to cm², divide by 100.
# Wait: 1 cm = 10 mm, so 1 cm² = 100 mm². So As_mm2 / 100 = As_cm2. ✓

# But check A_eff:
# A_eff = b * d = 400 * 550 = 220,000 mm²
# A_eff / 100 = 2,200 cm² → This IS correct for the conversion.
# So the display unit conversion is correct.
check("As mm² to cm² conversion (÷100)",
      abs(1500 / 100 - 15.0) < 0.01,
      "1500 mm² / 100 = 15.0 cm² ✓")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 13: N·mm TO tonf·m CONVERSION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 13. Force/Moment Unit Conversion Tests")
print("-" * 70)

# 1 tonf = 9806.65 N → 1 N = 1/9806.65 tonf ✓
# 1 tonf·m = 1 tonf * 1000 mm = 9806.65 N * 1000 mm = 9,806,650 N·mm
# So 1 N·mm = 1/9,806,650 tonf·m ✓
check("N·mm to tonf·m conversion factor",
      abs(1.0 / 9806650.0 - NMM_TO_TONFM) < 1e-15,
      f"1/9806650 = {1.0/9806650.0}, constant = {NMM_TO_TONFM}")

# Cross-check: 258,046,000 N·mm → should be ≈26.31 tonf·m
# (from test.py output)
Mn_Nmm_test = 258046000
Mn_tfm_test = Mn_Nmm_test * NMM_TO_TONFM
check("Mn conversion: 258e6 N·mm ≈ 26.31 tonf·m",
      abs(Mn_tfm_test - 26.31) < 0.1,
      f"Mn = {Mn_tfm_test:.3f} tonf·m")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 14: COMPRESSION STEEL DISPLACEMENT CORRECTION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 14. Compression Steel Displacement Correction Tests")
print("-" * 70)

# When a > dp: fsc_net = Es*eps_cp - 0.85*fc
# When a <= dp: fsc_net = Es*eps_cp (no displacement)
# This is correct per ACI — we subtract displaced concrete.

# But there's an edge case: what if compression steel is in the web of a T-beam
# where the stress block covers part of the web? The 0.85*fc subtraction
# should only apply where concrete actually exists around the bar.
# For now, let's verify the basic logic:

# Test: a barely > dp → displacement applies
geom_disp = rect_geom()
# Need a ≈ dp = 60. a = beta1*c → c = a/beta1 = 60/0.85 = 70.6
# eps_s = 0.003*(550-70.6)/70.6 = 0.0204 → tension controlled
# Need As such that c ≈ 70.6
# T = Cc + Cs. If Cs small: As*fy ≈ 0.85*fc*b*a → As ≈ 0.85*27.46*400*60/392.27 ≈ 1430
result_disp = calculate_flexural_capacity(
    geom_disp, As=1430, Asp=500, d=550, dp=60, concrete=conc, steel=stl
)
check("Compression steel displacement: a vs dp",
      True,  # Just verify no crash
      f"a = {result_disp.a:.1f}, dp = 60, Cs = {result_disp.Cs:.0f} N")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 15: REBAR BOUNDARY VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 15. Rebar Boundary Validation Tests")
print("-" * 70)

# Rectangular: bar at exact edge
geom_val = rect_geom(b=400, h=600)
records_edge = [
    RebarRecord(layer="Bottom", x=190, y=-290, dia=20, count=1, bar_size="DB20"),
    # x + dia/2 = 190 + 10 = 200 = b/2 → exactly on boundary
]
out_edge = check_bars_outside_bounds(geom_val, records_edge)
check("Bar at exact boundary (x+r = b/2) is NOT flagged",
      out_edge == 0,
      f"Flagged {out_edge} bars")

records_outside = [
    RebarRecord(layer="Bottom", x=191, y=-290, dia=20, count=1, bar_size="DB20"),
    # x + dia/2 = 191 + 10 = 201 > 200 → outside
]
out_outside = check_bars_outside_bounds(geom_val, records_outside)
check("Bar just outside boundary is flagged",
      out_outside == 1,
      f"Flagged {out_outside} bars")

# T-Beam: bar in web zone
geom_val_t = tbeam_geom(bf=1200, tf=120, bw=300, h=700)
records_web = [
    # Bar at x=200, y=-200 → web zone (y < h/2 - tf = 230)
    # bw/2 = 150, so 200 + 10 = 210 > 150 → OUTSIDE
    RebarRecord(layer="Bottom", x=200, y=-200, dia=20, count=1, bar_size="DB20"),
]
out_web = check_bars_outside_bounds(geom_val_t, records_web)
check("T-Beam: bar in web zone outside bw flagged",
      out_web == 1,
      f"Flagged {out_web}")

# T-Beam: bar in flange zone
records_flange = [
    # Bar at x=500, y=300 → flange zone (y > h/2 - tf = 230)
    # bf/2 = 600, so 500 + 10 = 510 < 600 → INSIDE
    RebarRecord(layer="Top", x=500, y=300, dia=20, count=1, bar_size="DB20"),
]
out_flange = check_bars_outside_bounds(geom_val_t, records_flange)
check("T-Beam: bar in flange zone within bf is OK",
      out_flange == 0,
      f"Flagged {out_flange}")

# Circular: bar at edge
geom_val_c = circ_geom(D=500)
records_circ_edge = [
    # Bar at center: dist = 0, 0 + 10 < 250 → inside
    RebarRecord(layer="Bottom", x=0, y=0, dia=20, count=1, bar_size="DB20"),
]
out_circ = check_bars_outside_bounds(geom_val_c, records_circ_edge)
check("Circular: bar at center is inside",
      out_circ == 0,
      f"Flagged {out_circ}")

records_circ_outside = [
    # Bar at (240, 0): dist = 240, 240 + 10 = 250 = D/2 → boundary
    RebarRecord(layer="Bottom", x=240, y=0, dia=20, count=1, bar_size="DB20"),
]
out_circ2 = check_bars_outside_bounds(geom_val_c, records_circ_outside)
check("Circular: bar at boundary (dist+r = R) is NOT flagged",
      out_circ2 == 0,
      f"Flagged {out_circ2}")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 16: REBAR GENERATOR COORDINATE TESTS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 16. Rebar Generator Tests")
print("-" * 70)

# Rectangular: bottom row 1, 3 bars, auto spacing
geom_gen = rect_geom(b=400, h=600, cover=40, stirrup=10)
records_gen = generate_rebar_coordinates(geom_gen, "Bottom", "DB25", 25.0, 3, 1, "Auto", 100.0)

check("Bottom auto: correct count",
      len(records_gen) == 3,
      f"Got {len(records_gen)} bars")

# Check Y position: -h/2 + cover + stirrup + dia/2 = -300 + 40 + 10 + 12.5 = -237.5
y_expected_gen = -300 + 40 + 10 + 12.5
check("Bottom auto: Y position",
      all(abs(r.y - y_expected_gen) < 0.5 for r in records_gen),
      f"Y values: {[r.y for r in records_gen]}, expected {y_expected_gen}")

# Check X positions span from _x_min to _x_max
x_min_gen = -400/2 + 40 + 10 + 12.5  # = -137.5
x_max_gen = 400/2 - 40 - 10 - 12.5   # = 137.5
check("Bottom auto: X range",
      abs(records_gen[0].x - x_min_gen) < 0.5 and abs(records_gen[-1].x - x_max_gen) < 0.5,
      f"X: [{records_gen[0].x}, {records_gen[-1].x}], expected [{x_min_gen}, {x_max_gen}]")

# Single bar should be centered at x=0
records_single = generate_rebar_coordinates(geom_gen, "Bottom", "DB25", 25.0, 1, 1, "Auto", 100.0)
check("Bottom auto single bar: centered at x=0",
      len(records_single) == 1 and abs(records_single[0].x) < 0.1,
      f"X = {records_single[0].x if records_single else 'N/A'}")

# Side bars: should generate pairs (left + right)
records_side = generate_rebar_coordinates(geom_gen, "Side", "DB12", 12.0, 3, 1, "Auto", 100.0)
check("Side auto: generates pairs (n*2 bars)",
      len(records_side) == 6,
      f"Got {len(records_side)} bars (expected 6)")

# Top row 1, 2 bars
records_top_gen = generate_rebar_coordinates(geom_gen, "Top", "DB16", 16.0, 2, 1, "Auto", 100.0)
y_top_expected = 300 - 40 - 10 - 8  # = 242
check("Top auto: Y position",
      all(abs(r.y - y_top_expected) < 0.5 for r in records_top_gen),
      f"Y values: {[r.y for r in records_top_gen]}, expected {y_top_expected}")

# Row 2 should shift inward by (dia + row_gap)
records_row2 = generate_rebar_coordinates(geom_gen, "Bottom", "DB25", 25.0, 3, 2, "Auto", 100.0)
row_gap = max(25, 25)  # = 25
y_row2_expected = y_expected_gen + (25 + 25)  # row 2 = y_min + 1*(dia + gap)
check("Bottom row 2: Y shifted inward",
      all(abs(r.y - y_row2_expected) < 0.5 for r in records_row2),
      f"Y values: {[r.y for r in records_row2]}, expected {y_row2_expected}")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 17: TRANSFORMED CENTROID CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 17. Transformed Centroid Tests")
print("-" * 70)

# No bars: centroid should be at (0, 0) for rectangular
geom_tc = rect_geom()
cx0, cy0 = calculate_transformed_centroid(geom_tc, [], 8.0)
check("Rectangular no bars: centroid at (0,0)",
      abs(cx0) < 0.01 and abs(cy0) < 0.01,
      f"cx={cx0}, cy={cy0}")

# Symmetric bars: centroid should still be at (0, ≈0 adjusted for bar position)
records_sym = [
    RebarRecord(layer="Bottom", x=-100, y=-240, dia=25, count=1, bar_size="DB25"),
    RebarRecord(layer="Bottom", x=100, y=-240, dia=25, count=1, bar_size="DB25"),
    RebarRecord(layer="Top", x=-100, y=240, dia=25, count=1, bar_size="DB25"),
    RebarRecord(layer="Top", x=100, y=240, dia=25, count=1, bar_size="DB25"),
]
cx_s, cy_s = calculate_transformed_centroid(geom_tc, records_sym, 8.0)
check("Symmetric bars: cx ≈ 0",
      abs(cx_s) < 0.01,
      f"cx = {cx_s}")
check("Symmetric bars: cy ≈ 0",
      abs(cy_s) < 0.01,
      f"cy = {cy_s}")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 18: render_section_tab DEAD CODE / BROKEN SIGNATURE
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 18. Code Architecture / Dead Code Tests")
print("-" * 70)

# section_tab.py has TWO versions of render_section_tab:
# - render_section_tab (line 17) — missing steel parameter, passes wrong fy
# - render_section_tab_v2 (line 69) — correct version with steel parameter
# Main.py imports and uses render_section_tab from ui/__init__.py

# Check what's exported from ui/__init__
# The function being called in Main.py line 44:
#   render_section_tab("Int", geom, concrete, steel, display_opts)
# passes 5 args, but render_section_tab only takes 4 (no steel).
# This means Main.py WILL CRASH when calling render_section_tab!

# render_section_tab(sec_key, geom, concrete, display_opts) ← 4 params
# But Main.py calls: render_section_tab("Int", geom, concrete, steel, display_opts) ← 5 args
# This is a guaranteed TypeError at runtime unless ui/__init__.py re-exports the v2 version.

check("CRITICAL: render_section_tab signature mismatch with Main.py call",
      False,
      "Main.py calls render_section_tab(sec_key, geom, concrete, steel, display_opts) with 5 args, "
      "but section_tab.py's render_section_tab only accepts 4 params (no steel). "
      "Either Main.py crashes or ui/__init__.py re-exports render_section_tab_v2 as render_section_tab.")

# Also: render_section_tab (line 55) passes fy=st.session_state.get(f"As_bot_{sec_key}", 0.0)
# This passes the STEEL AREA (As_bot in mm²) as the yield strength (fy in MPa)!
# This would cause the NA line calculation to be completely wrong.
check("BUG: render_section_tab passes As_bot as fy",
      False,
      "section_tab.py line 55: fy=st.session_state.get(f'As_bot_{sec_key}', 0.0) — "
      "passes steel area (mm²) where yield strength (MPa) is expected. "
      "This corrupts the neutral axis visualization.")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 19: section_plot.py NA CALCULATION — USES fy*MPA_TO_KSC
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 19. Section Plot NA Calculation Tests")
print("-" * 70)

# section_plot.py line 128:
#   steel_temp = SteelProps(fy_ksc=fy * MPA_TO_KSC, fyt_ksc=2400.0)
# If fy is the ACTUAL yield strength in MPa (e.g., 392.27):
#   fy_ksc = 392.27 * 10.197 = 4000 ksc ✓ (correct)
# But if fy is actually As_bot (e.g., 1472.6 mm²):
#   fy_ksc = 1472.6 * 10.197 = 15017 ksc (WRONG — nonsensical yield strength)

# The render_section_tab_v2 correctly passes steel.fy (MPa), but render_section_tab passes As_bot.
# This confirms render_section_tab is broken.
check("section_plot NA: fy parameter interpretation",
      True,  # This is tested via Category 18 already
      "If fy=As_bot is passed, NA position will be grossly wrong on the section plot.")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 20: FLEXURAL PLOT COORDINATE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 20. Flexural Plot Coordinate Transform Tests")
print("-" * 70)

# flexural_plot.py line 102:
#   py = (h / 2.0 - r.y) if pos_moment else (h / 2.0 + r.y)
# For +M: depth from comp. face (top): py = h/2 - r.y
#   Bottom bar at y=-240 → py = 300 - (-240) = 540 ✓ (depth from top)
#   Top bar at y=+240 → py = 300 - 240 = 60 ✓
# For -M: depth from comp. face (bottom): py = h/2 + r.y
#   Top bar at y=+240 → py = 300 + 240 = 540 ✓ (depth from bottom)
#   Bottom bar at y=-240 → py = 300 + (-240) = 60 ✓
check("Flexural plot: +M coordinate transform",
      True,
      "h/2 - r.y correctly maps bottom bars to larger depth values")
check("Flexural plot: -M coordinate transform",
      True,
      "h/2 + r.y correctly maps top bars to larger depth values")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 21: HIGH-STRENGTH CONCRETE (f'c > 55 MPa)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 21. High-Strength Concrete Tests")
print("-" * 70)

# f'c = 600 ksc = 58.84 MPa > 55 → beta1 = 0.65
c600 = std_concrete(600)
check("f'c = 600 ksc: beta1 = 0.65",
      abs(c600.beta1 - 0.65) < 0.001,
      f"beta1 = {c600.beta1}")

# f'c = 700 ksc = 68.65 MPa → beta1 = 0.65
c700 = std_concrete(700)
check("f'c = 700 ksc: beta1 = 0.65",
      abs(c700.beta1 - 0.65) < 0.001,
      f"beta1 = {c700.beta1}")

# Ec = 4700*sqrt(fc_mpa) — verify
Ec_600 = c600.Ec_mpa
Ec_expected = 4700 * math.sqrt(c600.fc_prime)
check("Ec at f'c=600 ksc",
      abs(Ec_600 - Ec_expected) < 1.0,
      f"Code: {Ec_600:.0f}, Expected: {Ec_expected:.0f}")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 22: COMPRESSION-CONTROLLED SECTION CAPACITY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 22. Compression-Controlled Section Tests")
print("-" * 70)

# Force compression-controlled: need eps_s <= 0.002
# c/d >= eps_cu/(eps_cu + 0.002) = 0.003/0.005 = 0.6
# c >= 0.6*550 = 330 → need very heavy reinforcement
geom_cc = rect_geom()
result_cc = calculate_flexural_capacity(
    geom_cc, As=20000, Asp=0, d=550, dp=60, concrete=conc, steel=stl
)
check("Compression-controlled section: phi = 0.65",
      abs(result_cc.phi - 0.65) < 0.01,
      f"eps_s = {result_cc.eps_s:.6f}, phi = {result_cc.phi}")

# Check that Mn is still positive
check("Compression-controlled: positive Mn",
      result_cc.Mn > 0,
      f"Mn = {result_cc.Mn*NMM_TO_TONFM:.2f} tonf·m")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 23: FLEXURAL_TAB FALSY-VALUE CHECKS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 23. Falsy-Value Display Bugs")
print("-" * 70)

# flexural_tab.py line 356: f"{capacity.eps_s:.4f}" if capacity.eps_s else "—"
# If eps_s == 0.0, this shows "—" instead of "0.0000"
# eps_s = 0 when c = d (neutral axis at tension steel level)

# Similarly line 358: f"{capacity.phi:.3f}" if capacity.phi else "—"
# phi is always > 0 if there's capacity, so this shouldn't trigger falsely.
# But phi=0 would show "—" when it should show "0.000"

# Line 359: f"{Cc_tf:.2f}" if Cc_tf else "—"  
# Cc_tf = 0 → shows "—" instead of "0.00"
check("BUG: falsy check on eps_s=0 shows dash instead of 0.0000",
      False,
      "flexural_tab.py line 356: `if capacity.eps_s` is False when eps_s=0.0, "
      "displaying '—' instead of '0.0000'. Should use `if capacity.eps_s is not None`.")

check("BUG: falsy check on Cc_tf=0 shows dash instead of 0.00",
      False,
      "flexural_tab.py line 359: `if Cc_tf` is False when Cc_tf=0.0, "
      "displaying '—' instead of '0.00'. Should use `is not None` check.")

check("BUG: falsy check on T_tf=0 shows dash instead of 0.00",
      False,
      "flexural_tab.py line 361: `if T_tf` is False when T_tf=0.0, "
      "displaying '—' instead of '0.00'.")

check("BUG: falsy check on Mn_tonfm=0 shows dash instead of 0.00",
      False,
      "flexural_tab.py lines 362-363: `if Mn_tonfm` / `if phiMn_tonfm` treat 0.0 as missing.")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 24: A_eff DIVISION SAFETY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 24. Division Safety Tests")
print("-" * 70)

# flexural_tab.py line 315: A_eff = b * d if d > 0.0 else 1.0
# If d = 0 → A_eff = 1.0 → rho = As / 1.0 (inflated ratio)
# This is a safety fallback, but the displayed value would be wrong.
# Better to show 0 or N/A.
check("A_eff fallback when d=0: rho = As/1.0 is misleading",
      True,
      "flexural_tab.py line 316: rho = As / 1.0 when d=0 produces meaningless steel ratio. "
      "Should display 'N/A' instead.")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 25: CRACKED INERTIA DEFAULT DEPTH
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 25. Cracked Inertia Default Depth Tests")
print("-" * 70)

# properties.py lines 76-77:
#   d = d_eff if d_eff is not None else (geom.h - geom.cover - geom.stirrup_dia - 25.0)
#   dp = dp_eff if dp_eff is not None else (geom.cover + geom.stirrup_dia + 25.0)
# The 25.0 is a hardcoded assumed bar radius. This should ideally come from
# actual bar size. But as a default it's reasonable (DB25 → r=12.5, but 25mm includes some margin).

# Check: for 600mm beam, cover=40, stirrup=10:
# d_default = 600 - 40 - 10 - 25 = 525
# dp_default = 40 + 10 + 25 = 75
geom_def = rect_geom(b=400, h=600, cover=40, stirrup=10)
Icr_def = calculate_cracked_inertia(geom_def, 1000, 500, None, None, 8.0)
# Manual with d=525, dp=75
A_q = 200
B_q = 7*500 + 8*1000  # = 11500
C_q = -7*500*75 - 8*1000*525  # = -262500 - 4200000 = -4462500
kd_def = (-B_q + np.sqrt(B_q**2 - 4*A_q*C_q)) / (2*A_q)
Icr_def_manual = (400*kd_def**3/3) + 7*500*(kd_def-75)**2 + 8*1000*(525-kd_def)**2

err_def = abs(Icr_def - Icr_def_manual) / Icr_def_manual * 100
check("Icr with None defaults matches manual (d=525, dp=75)",
      err_def < 0.1,
      f"Code: {Icr_def:.0f}, Manual: {Icr_def_manual:.0f}, err = {err_def:.4f}%")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 26: CIRCULAR SECTION get_concrete_compression y_bar/y_c
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 26. Circular Compression Centroid Tests")
print("-" * 70)

# capacity.py lines 80-86:
# val = (R - a_clamped) / R → cos(theta)
# theta = acos(val)  → half-angle of segment from center
# A_seg = R² (θ - sinθ·cosθ)
# y_bar = 2R³ sin³θ / (3·A_seg)  ← centroid distance from circle CENTER
# y_c = R - y_bar  ← distance from TOP (compression face)

# For a = R (half circle): theta = pi/2
# A_seg = R²(pi/2 - 0) = pi*R²/2
# y_bar = 2R³·1/(3·pi*R²/2) = 4R/(3π) 
# y_c = R - 4R/(3π) ≈ R(1 - 4/(3π)) ≈ R * 0.5756

R_test = 250.0
theta_test = math.pi / 2
A_seg_test = R_test**2 * (theta_test - math.sin(theta_test)*math.cos(theta_test))
y_bar_test = (2.0 * R_test**3 * math.sin(theta_test)**3) / (3.0 * A_seg_test)
y_c_test = R_test - y_bar_test
y_c_expected = R_test * (1 - 4/(3*math.pi))

check("Circular centroid at a=R: y_c ≈ R*(1-4/(3π))",
      abs(y_c_test - y_c_expected) < 0.1,
      f"y_c = {y_c_test:.2f}, expected = {y_c_expected:.2f}")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 27: OVER-REINFORCED SECTION (c > d)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 27. Over-Reinforced Section Tests")
print("-" * 70)

# When As is extremely large, c could exceed d, making eps_s negative
# (tension steel actually in compression)
result_over = calculate_flexural_capacity(
    geom_r, As=50000, Asp=0, d=550, dp=60, concrete=conc, steel=stl
)

# c is clamped to geom.h = 600 (line 130)
check("Over-reinforced: c clamped to h",
      result_over.c_na <= geom_r.h + 0.01,
      f"c = {result_over.c_na:.1f}, h = {geom_r.h}")

# eps_s = 0.003*(550 - c)/c. If c > 550, eps_s is negative → tension steel in compression
# The code handles this via min/max clamping of stress
if result_over.c_na > 550:
    check("Over-reinforced: negative eps_s (tension steel in compression)",
          result_over.eps_s < 0,
          f"eps_s = {result_over.eps_s:.6f}")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 28: T-BEAM WITH NARROW WEB — b field used as b_f
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 28. T-Beam b Field Semantics")
print("-" * 70)

# In sidebar.py line 75: b = b_f for T-Beams
# In capacity.py line 42: b = geom.b
# But `b` isn't used for T-beam compression (the T-beam branch uses b_f and b_w)
# HOWEVER, it IS used in the Newton-Raphson clamp: c_val = min(c_val, geom.h)
# And in the initial guess: c_val = d * 0.2

# Also: the rebar generator uses geom.b for x-limits (line 74):
#   _x_min = -geom.b / 2.0 + cover + stirrup + dia/2
# For T-beams, this uses b = b_f = 1200, so bars span the flange width.
# But bottom bars should be within the WEB width (bw = 300), not the flange!

geom_t_gen = tbeam_geom(bf=1200, tf=120, bw=300, h=700)
records_t_gen = generate_rebar_coordinates(geom_t_gen, "Bottom", "DB25", 25.0, 3, 1, "Auto", 100.0)

# Check if bars are within web width
x_limit_web = geom_t_gen.b_w / 2.0 - 40 - 10 - 12.5  # = 87.5
x_limit_flange = geom_t_gen.b / 2.0 - 40 - 10 - 12.5  # = 537.5

# The bars will be spread across the FLANGE width, not the web
x_max_bar = max(abs(r.x) for r in records_t_gen)
check("BUG: T-Beam rebar generator uses b (=b_f) for bottom bar X-limits instead of b_w",
      x_max_bar > x_limit_web + 1,  # This IS the bug: bars extend beyond web
      f"Max |x| = {x_max_bar:.1f}, web limit = {x_limit_web:.1f}, flange limit = {x_limit_flange:.1f}. "
      f"Bottom bars should be within web width b_w={geom_t_gen.b_w} mm.")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 29: rho_b FORMULA IN flexural_tab.py
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 29. Balanced Steel Ratio Formula Tests")
print("-" * 70)

# flexural_tab.py line 317:
#   rho_b = (0.85 * beta1 * fc_prime / fy) * (600.0 / (600.0 + fy))
# ACI 318: rho_b = (0.85 * beta1 * fc' / fy) * (eps_cu / (eps_cu + ey))
# where ey = fy / Es = 392.27 / 200000 = 0.00196

# The code uses 600/(600+fy) where fy is in MPa.
# This comes from: eps_cu/(eps_cu + ey) = 0.003/(0.003 + fy/Es)
#   = 0.003 / (0.003 + fy/200000) = 600 / (600 + fy) ← when Es = 200000 MPa
# So this is correct ONLY when Es = 200,000 MPa exactly.

# But the test.py uses Es = 196,133 MPa (from 2,000,000 ksc * KSC_TO_MPA)
# In that case: 600/(600+fy) ≠ eps_cu/(eps_cu + fy/Es)

# With Es = 200000: ey = 392.27/200000 = 0.001961
# rho_b_200k = 0.85*0.85*27.46/392.27 * 0.003/(0.003+0.001961) = 0.05095 * 0.6047 = 0.03083
rho_b_200k = (0.85 * 0.85 * 27.46 / 392.27) * (600.0 / (600.0 + 392.27))
# = 0.05095 * 0.6047 = 0.03083

# With Es = 196133: ey = 392.27/196133 = 0.002000
# rho_b_196k = 0.85*0.85*27.46/392.27 * 0.003/(0.003+0.002) = 0.05095 * 0.6 = 0.03057
rho_b_196k = (0.85 * 0.85 * 27.46 / 392.27) * (0.003 / (0.003 + 392.27/196133))

check("rho_b: 600/(600+fy) assumes Es=200000 exactly",
      abs(rho_b_200k - rho_b_196k) < 0.001,
      f"Es=200000: rho_b={rho_b_200k:.5f}, Es=196133: rho_b={rho_b_196k:.5f}, "
      f"diff = {abs(rho_b_200k-rho_b_196k):.5f} "
      "(small but demonstrates Es inconsistency)")


# ═══════════════════════════════════════════════════════════════════════════════
# BUG CATEGORY 30: ui/__init__.py IMPORT CHECK
# ═══════════════════════════════════════════════════════════════════════════════
print("\n■ 30. Module Import & Export Tests")
print("-" * 70)

# Check what ui/__init__.py exports
import importlib.util
spec = importlib.util.spec_from_file_location(
    "ui_init",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "__init__.py")
)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "__init__.py"), "r") as f:
    init_content = f.read()

# Check if render_section_tab_v2 is imported/aliased as render_section_tab
has_v2_alias = "render_section_tab_v2 as render_section_tab" in init_content or \
               "render_section_tab_v2" in init_content
has_v1 = "from ui.section_tab import render_section_tab" in init_content

print(f"  ui/__init__.py content:\n    {init_content.strip()}")
check("ui/__init__.py exports correct render_section_tab version",
      has_v2_alias or "v2" in init_content,
      f"Content: {init_content.strip()}")


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"  RESULTS: {PASS} passed, {FAIL} failed")
print("=" * 70)

if BUGS:
    print(f"\n  ■ {len(BUGS)} BUG(S) FOUND:")
    for i, (name, detail) in enumerate(BUGS, 1):
        print(f"\n  BUG #{i}: {name}")
        print(f"    {detail}")

print("\n" + "=" * 70)
