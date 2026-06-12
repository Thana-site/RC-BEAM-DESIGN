"""
ACI 318 Flexural Capacity - Refactored Solver Regression Test
"""
import math
import sys
import os

# Append current directory to path so we can import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.section import SectionGeometry
from models.materials import ConcreteProps, SteelProps
from analysis.capacity import calculate_flexural_capacity

def run_test():
    # Inputs matching test.py
    b = 400.0
    h = 600.0
    d = 550.0
    d_prime = 60.0
    
    # DB20 steel area (math.pi * 20^2 / 4)
    # 4 x DB20 bottom (tension)
    As_bot = 4.0 * (math.pi * 20.0**2 / 4.0)
    # 2 x DB20 top (compression)
    As_top = 2.0 * (math.pi * 20.0**2 / 4.0)
    
    # Instantiate models
    geom = SectionGeometry(section_type="Rectangular", b=b, h=h, cover=40.0, stirrup_dia=10.0)
    concrete = ConcreteProps(fc_ksc=280.0)
    # Note: test.py uses Es = 2,000,000 ksc, which is 196,133 MPa.
    # We will pass the exact Es = 196133.0 to verify exact matches with test.py.
    steel = SteelProps(fy_ksc=4000.0, fyt_ksc=2400.0, Es_mpa=196133.00)
    
    result = calculate_flexural_capacity(
        geom=geom,
        As=As_bot,
        Asp=As_top,
        d=d,
        dp=d_prime,
        concrete=concrete,
        steel=steel
    )
    
    # conversion factors
    N_TO_TONF = 1.0 / 9806.65
    NMM_TO_TONFM = 1.0 / 9806650.0
    
    T_tonf = result.T * N_TO_TONF
    Cc_tonf = result.Cc * N_TO_TONF
    Cs_tonf = result.Cs * N_TO_TONF
    C_tonf = Cc_tonf + Cs_tonf
    Mn_tonfm = result.Mn * NMM_TO_TONFM
    phiMn_tonfm = result.phi_Mn * NMM_TO_TONFM
    
    err_pct = abs(result.T - (result.Cc + result.Cs)) / max(result.T, 1) * 100
    
    print("=" * 60)
    print("  ACI 318 Flexural Capacity  -  Refactored Solver Verification")
    print("=" * 60)
    print("\n[GEOMETRY & MATERIALS]")
    print(f"  b          = {geom.b:.0f} mm")
    print(f"  h          = {geom.h:.0f} mm")
    print(f"  d          = {d:.0f} mm")
    print(f"  d'         = {d_prime:.0f} mm")
    print(f"  As,bot     = {As_bot:.1f} mm2")
    print(f"  As,top     = {As_top:.1f} mm2")
    print(f"  f'c        = {concrete.fc_ksc:.0f} ksc  ({concrete.fc_prime:.2f} MPa)")
    print(f"  fy         = {steel.fy_ksc:.0f} ksc  ({steel.fy:.2f} MPa)")
    print(f"  Es         = {steel.Es_mpa:.0f} MPa")
    print(f"  beta1      = {concrete.beta1:.4f}")
    
    print(f"\n[SOLVER OUTPUT]")
    print(f"  c  (NA)    = {result.c_na:.2f} mm")
    print(f"  a  (block) = {result.a:.2f} mm")
    print(f"  eps_t      = {result.eps_s:.4f}")
    print(f"  eps_c      = {result.eps_cp:.4f}")
    print(f"  phi        = {result.phi:.4f}")
    print(f"  T          = {T_tonf:.3f} tonf")
    print(f"  Cc         = {Cc_tonf:.3f} tonf")
    print(f"  Cs         = {Cs_tonf:.3f} tonf")
    print(f"  C          = {C_tonf:.3f} tonf")
    print(f"  |T - C|/T  = {err_pct:.6f} %")
    print(f"  Mn         = {Mn_tonfm:.3f} tonf.m")
    print(f"  phi.Mn     = {phiMn_tonfm:.3f} tonf.m")
    print("=" * 60)

if __name__ == "__main__":
    run_test()
