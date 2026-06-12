"""
RC Section Visualizer — Flexural Capacity Solver
"""
import math
from dataclasses import dataclass
from models.section import SectionGeometry
from models.materials import ConcreteProps, SteelProps

@dataclass
class CapacityResult:
    c_na: float       # Neutral axis depth (mm)
    a: float          # Stress block depth (mm)
    eps_s: float      # Tension steel strain
    eps_cp: float     # Compression steel strain
    phi: float        # Strength reduction factor
    T: float          # Tension steel force (N)
    Cc: float         # Concrete block compression force (N)
    Cs: float         # Compression steel force (N)
    Mn: float         # Nominal moment capacity (N·mm)
    phi_Mn: float     # Design moment capacity (N·mm)

def calculate_flexural_capacity(
    geom: SectionGeometry,
    As: float,
    Asp: float,
    d: float,
    dp: float,
    concrete: ConcreteProps,
    steel: SteelProps
) -> CapacityResult:
    """
    Solve doubly-reinforced concrete beam flexural capacity using ACI 318
    and Newton-Raphson iteration.
    
    All inputs and calculations use MPa, N, and mm.
    """
    Es = steel.Es_mpa
    eps_cu = 0.003
    fc_prime = concrete.fc_prime
    fy = steel.fy
    b1 = concrete.beta1
    b = geom.b

    # Safety check for invalid input geometry
    if d <= dp or As <= 0 or d <= 0:
        return CapacityResult(
            c_na=0.0,
            a=0.0,
            eps_s=0.0,
            eps_cp=0.0,
            phi=0.65,
            T=0.0,
            Cc=0.0,
            Cs=0.0,
            Mn=0.0,
            phi_Mn=0.0
        )

    # Concrete compression force and centroid height calculation
    def get_concrete_compression(a_val: float) -> tuple[float, float]:
        """
        Returns (Cc_force, y_comp)
        where y_comp is the distance from the compression face to the centroid of Cc.
        """
        if geom.section_type == "T-Beam":
            if a_val <= geom.t_f:
                force = 0.85 * fc_prime * geom.b_f * a_val
                y_c = a_val / 2.0
            else:
                F_flange = 0.85 * fc_prime * (geom.b_f - geom.b_w) * geom.t_f
                F_web = 0.85 * fc_prime * geom.b_w * a_val
                force = F_flange + F_web
                y_c = (F_flange * (geom.t_f / 2.0) + F_web * (a_val / 2.0)) / force if force > 0.0 else 0.0
            return force, y_c
        elif geom.section_type == "Circular":
            R = geom.D / 2.0
            a_clamped = max(0.0, min(a_val, geom.D))
            if a_clamped <= 0.0:
                return 0.0, 0.0
            val = (R - a_clamped) / R
            val = max(-1.0, min(val, 1.0))
            theta = math.acos(val)
            A_seg = R**2 * (theta - math.sin(theta) * math.cos(theta))
            force = 0.85 * fc_prime * A_seg
            y_bar = (2.0 * R**3 * (math.sin(theta))**3) / (3.0 * A_seg) if A_seg > 0 else 0.0
            y_c = R - y_bar
            return force, y_c
        else: # Rectangular
            force = 0.85 * fc_prime * geom.b * a_val
            y_c = a_val / 2.0
            return force, y_c

    # Newton-Raphson force balance equation solver
    def force_balance(c: float) -> float:
        a_val = b1 * c
        # Tension steel strain & stress (bounded at -fy in compression)
        fst = min(max(Es * eps_cu * (d - c) / c, -fy), fy)
        # Compression steel strain & stress
        ec = eps_cu * (c - dp) / c
        # Net compression steel stress accounting for displaced concrete
        fsc = min(max(Es * ec, -fy), fy) - (0.85 * fc_prime if a_val > dp else 0.0)
        
        T_force = As * fst
        Cc_force, _ = get_concrete_compression(a_val)
        Cs_force = Asp * fsc
        return T_force - (Cc_force + Cs_force)

    def force_balance_derivative(c: float, dh: float = 1e-3) -> float:
        return (force_balance(c + dh) - force_balance(c - dh)) / (2.0 * dh)

    # Solve for NA depth c
    c_na = 0.0
    a = 0.0
    eps_s = 0.0
    eps_cp = 0.0
    phi = 0.65
    T_N = Cc_N = Cs_N = 0.0
    Mn = phi_Mn = 0.0

    c_val = d * 0.2
    for _ in range(60):
        F = force_balance(c_val)
        if abs(F) < 1e-4:
            break
        dF = force_balance_derivative(c_val)
        if abs(dF) < 1e-12:
            break
        c_val -= F / dF
        c_val = max(c_val, 1.0)       # Avoid division by zero
        c_val = min(c_val, geom.h)    # Limit NA search to beam height

    c_na = c_val
    a = b1 * c_na
    eps_s = eps_cu * (d - c_na) / c_na
    eps_cp = eps_cu * (c_na - dp) / c_na

    _fsc_net = min(max(Es * eps_cp, -fy), fy) - (0.85 * fc_prime if a > dp else 0.0)
    _fst = min(max(Es * eps_s, -fy), fy)

    # phi factor determination (ACI 318-19 Sec 21.2.2)
    if eps_s >= 0.005:
        phi = 0.90
    elif eps_s <= 0.002:
        phi = 0.65
    else:
        phi = 0.65 + (eps_s - 0.002) * (250.0 / 3.0)

    T_N = As * _fst
    Cc_N, y_comp = get_concrete_compression(a)
    Cs_N = Asp * _fsc_net
    Mn = Cc_N * (d - y_comp) + Cs_N * (d - dp)
    phi_Mn = phi * Mn

    return CapacityResult(
        c_na=c_na,
        a=a,
        eps_s=eps_s,
        eps_cp=eps_cp,
        phi=phi,
        T=T_N,
        Cc=Cc_N,
        Cs=Cs_N,
        Mn=Mn,
        phi_Mn=phi_Mn
    )

