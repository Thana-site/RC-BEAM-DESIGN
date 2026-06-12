"""
Automated unit tests to validate fixes for calculation, geometry, and boundary bugs in RC-BEAM-DESIGN.
"""
import math
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.section import SectionGeometry
from models.materials import ConcreteProps, SteelProps
from analysis.capacity import calculate_flexural_capacity
from analysis.properties import calculate_cracked_inertia
from analysis.validation import check_bars_outside_bounds
from analysis.rebar_generator import generate_rebar_coordinates
from models.rebar import RebarRecord

def test_tbeam_capacity_overestimation():
    print("--- Test 1: T-Beam Flexural Capacity Correctness ---")
    geom = SectionGeometry(section_type="T-Beam", b=1200.0, h=700.0, cover=40.0, stirrup_dia=10.0, b_f=1200.0, t_f=120.0, b_w=300.0)
    concrete = ConcreteProps(fc_ksc=280.0)  # fc_prime = 27.46 MPa
    steel = SteelProps(fy_ksc=4000.0, fyt_ksc=2400.0, Es_mpa=200000.0) # fy = 392.27 MPa
    
    result = calculate_flexural_capacity(
        geom=geom,
        As=11500.0,
        Asp=0.0,
        d=640.0,
        dp=60.0,
        concrete=concrete,
        steel=steel
    )
    
    NMM_TO_TONFM = 1.0 / 9806650.0
    Mn_code = result.Mn * NMM_TO_TONFM
    phiMn_code = result.phi_Mn * NMM_TO_TONFM
    c_code = result.c_na
    a_code = result.a
    phi_code = result.phi
    
    print(f"Codebase Solver Output:")
    print(f"  c (neutral axis) = {c_code:.2f} mm")
    print(f"  a (stress block) = {a_code:.2f} mm")
    print(f"  phi factor       = {phi_code:.4f}")
    print(f"  Mn               = {Mn_code:.2f} tonf.m")
    print(f"  phiMn            = {phiMn_code:.2f} tonf.m")
    
    # Correct values
    c_correct = 334.42
    a_correct = 284.26
    phi_correct = 0.7118
    Mn_correct = 250.13
    phiMn_correct = 178.03
    
    print("\nExpected Analytical Output:")
    print(f"  c (neutral axis) = {c_correct:.2f} mm")
    print(f"  a (stress block) = {a_correct:.2f} mm")
    print(f"  phi factor       = {phi_correct:.4f}")
    print(f"  Mn               = {Mn_correct:.2f} tonf.m")
    print(f"  phiMn            = {phiMn_correct:.2f} tonf.m")
    
    err_c = abs(c_code - c_correct) / c_correct * 100
    err_phiMn = abs(phiMn_code - phiMn_correct) / phiMn_correct * 100
    print(f"\nErrors after fix:")
    print(f"  Neutral axis error: {err_c:.2f}%")
    print(f"  Capacity error: {err_phiMn:.2f}%")
    
    assert err_c < 1.0, f"Neutral axis depth error remains: {err_c:.2f}%"
    assert err_phiMn < 1.0, f"Capacity error remains: {err_phiMn:.2f}%"
    print("Result: T-Beam flexural capacity calculation fixed and verified!\n")


def test_circular_capacity_failure():
    print("--- Test 2: Circular Section Capacity Correctness ---")
    geom = SectionGeometry(section_type="Circular", b=500.0, h=500.0, cover=40.0, stirrup_dia=10.0, D=500.0)
    concrete = ConcreteProps(fc_ksc=280.0)
    steel = SteelProps(fy_ksc=4000.0, fyt_ksc=2400.0, Es_mpa=200000.0)
    
    result = calculate_flexural_capacity(
        geom=geom,
        As=2000.0,
        Asp=0.0,
        d=440.0,
        dp=60.0,
        concrete=concrete,
        steel=steel
    )
    
    NMM_TO_TONFM = 1.0 / 9806650.0
    N_TO_TONF = 1.0 / 9806.65
    
    print(f"Codebase Solver Output for Circular section:")
    print(f"  c (neutral axis) = {result.c_na:.2f} mm")
    print(f"  a (stress block) = {result.a:.2f} mm")
    print(f"  Cc (concrete comp force) = {result.Cc * N_TO_TONF:.2f} tonf")
    print(f"  phiMn            = {result.phi_Mn * NMM_TO_TONFM:.2f} tonf.m")
    
    # Calculate segment area using solver output
    # R = 250 mm. height of segment is result.a
    R = 250.0
    a_val = result.a
    theta = math.acos((R - a_val) / R)
    true_area = R**2 * (theta - math.sin(theta) * math.cos(theta))
    
    fc_prime = concrete.fc_prime
    code_area = result.Cc / (0.85 * fc_prime)
    
    area_error_pct = abs(code_area - true_area) / true_area * 100
    print(f"  Concrete Area at depth a = {result.a:.2f} mm:")
    print(f"    Codebase calculation = {code_area:.1f} mm2")
    print(f"    Correct circular segment = {true_area:.1f} mm2")
    print(f"    Discrepancy in concrete area = {area_error_pct:.2f}%")
    
    assert area_error_pct < 1.0, f"Circular segment area error remains: {area_error_pct:.2f}%"
    print("Result: Circular section capacity calculation fixed and verified!\n")


def test_cracked_inertia_default_depth_bug():
    print("--- Test 3: Cracked Inertia Default Depth Correctness ---")
    geom = SectionGeometry(section_type="Rectangular", b=400.0, h=600.0, cover=40.0, stirrup_dia=10.0)
    
    # Call cracked inertia with default d and dp (passing None)
    Icr = calculate_cracked_inertia(
        geom=geom,
        As_bot=1000.0,
        As_top=500.0,
        d_eff=None,
        dp_eff=None,
        n=8.0
    )
    
    print(f"Codebase Cracked Inertia Icr = {Icr/1e8:.3f} x 10^8 mm4")
    
    # Correct calculation:
    d_correct = 525.0
    dp_correct = 75.0
    A_q = 200.0
    B_q = 11500.0
    C_q_correct = - (7 * 500 * dp_correct) - 8 * 1000 * d_correct
    kd_correct = (-B_q + np.sqrt(B_q**2 - 4.0 * A_q * C_q_correct)) / (2.0 * A_q)
    Icr_correct = (400.0 * kd_correct**3 / 3.0) + 7 * 500 * (kd_correct - dp_correct)**2 + 8 * 1000 * (d_correct - kd_correct)**2
    
    print(f"Correct Cracked Inertia Icr  = {Icr_correct/1e8:.3f} x 10^8 mm4")
    discrepancy_pct = abs(Icr - Icr_correct) / Icr_correct * 100
    print(f"Discrepancy in cracked inertia = {discrepancy_pct:.2f}%")
    
    assert discrepancy_pct < 1.0, f"Cracked inertia discrepancy remains: {discrepancy_pct:.2f}%"
    print("Result: Cracked inertia default effective depth bug fixed and verified!\n")


def test_tbeam_boundary_validation_failure():
    print("--- Test 4: T-Beam Boundary Validation Correctness ---")
    geom = SectionGeometry(section_type="T-Beam", b=1200.0, h=700.0, cover=40.0, stirrup_dia=10.0, b_f=1200.0, t_f=120.0, b_w=300.0)
    
    # Place a bottom rebar outside the web (b_w = 300 mm, so limits are x in [-150, 150])
    # Let's put a bar at x = 450 mm, which is way outside the web.
    # Let's place it at y = -200 mm (inside the web height zone).
    records = [
        RebarRecord(layer="Bottom", x=450.0, y=-200.0, dia=20.0, count=1, bar_size="DB20")
    ]
    
    out_count = check_bars_outside_bounds(geom, records)
    print(f"Placed a bar at X = 450 mm, Y = -200 mm in a T-beam with web width = 300 mm.")
    print(f"Validation function reports: {out_count} bar(s) outside bounds.")
    
    assert out_count == 1, "Validation failed to detect rebar outside web bounds!"
    print("Result: T-Beam boundary validation fixed and verified!\n")


def test_circular_rebar_generation_bug():
    print("--- Test 5: Circular Section Rebar Generation Correctness ---")
    geom = SectionGeometry(section_type="Circular", b=500.0, h=500.0, cover=40.0, stirrup_dia=10.0, D=500.0)
    
    # Generate 3 bottom rebars using the automatic generator
    records = generate_rebar_coordinates(geom, "Bottom", "DB20", 20.0, 3, 1, "Auto", 100.0)
    
    print("Generated 3 bars for a circular section of diameter D = 500 mm:")
    outside_found = False
    for i, r in enumerate(records):
        dist = np.sqrt(r.x**2 + r.y**2)
        total_dist = dist + r.dia / 2.0
        is_outside = total_dist > (geom.D / 2.0)
        print(f"  Bar {i+1}: X = {r.x} mm, Y = {r.y} mm, Radial distance = {dist:.1f} mm, Outer edge = {total_dist:.1f} mm (Limit = 250 mm) {'[OUTSIDE!]' if is_outside else '[OK]'}")
        if is_outside:
            outside_found = True
            
    assert not outside_found, "Circular section rebar generation placed bars outside boundary!"
    print("Result: Circular section rebar generation fixed and verified!\n")


def run_all_tests():
    print("=" * 60)
    print("       RC-BEAM-DESIGN BUG VALIDATION SUITE")
    print("=" * 60)
    test_tbeam_capacity_overestimation()
    test_circular_capacity_failure()
    test_cracked_inertia_default_depth_bug()
    test_tbeam_boundary_validation_failure()
    test_circular_rebar_generation_bug()
    print("=" * 60)
    print("All fixes successfully verified and validated!")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()
