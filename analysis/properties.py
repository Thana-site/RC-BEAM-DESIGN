"""
RC Section Visualizer — Section Analysis Calculations
"""
import numpy as np
from models.section import SectionGeometry
from models.rebar import RebarRecord
from utils.math_helpers import bar_area

def get_steel_area(records: list[RebarRecord], layer: str) -> float:
    """Return the total steel area (mm²) for a given layer."""
    return sum(bar_area(r.dia) * r.count for r in records if r.layer == layer)

def calculate_effective_depth(records: list[RebarRecord], layer: str, h: float) -> float | None:
    """
    Return effective depth d (mm) measured from TOP of beam to
    the area-weighted centroid of rebars in the given layer.
    Returns None if no bars found.
    Coord system: y=0 at mid-height, y=+h/2 at top, y=-h/2 at bottom.
    d = h/2 − ȳ   where ȳ = Σ(Aᵢ·yᵢ) / ΣAᵢ
    """
    layer_records = [r for r in records if r.layer == layer]
    pairs = [(bar_area(r.dia) * r.count, r.y) for r in layer_records]
    total_A = sum(a for a, _ in pairs)
    if total_A == 0:
        return None
    y_bar = sum(a * y for a, y in pairs) / total_A
    return h / 2.0 - y_bar

def calculate_transformed_centroid(geom: SectionGeometry, records: list[RebarRecord], n: float) -> tuple[float, float]:
    """
    Calculate the transformed centroid (cx, cy) of the concrete section + transformed steel.
    Returns (cx, cy) coordinates relative to the geometric center (mid-height/mid-width).
    """
    A_g = geom.Ag
    
    # Calculate concrete geometric centroid relative to mid-height (y=0)
    if geom.section_type == "T-Beam":
        A_f = geom.b_f * geom.t_f
        y_f = geom.h / 2.0 - geom.t_f / 2.0
        A_w = geom.b_w * (geom.h - geom.t_f)
        y_w = -geom.t_f / 2.0
        cy_concrete = (A_f * y_f + A_w * y_w) / (A_f + A_w)
    else:
        cy_concrete = 0.0
        
    if records:
        As_tot = sum(bar_area(r.dia) * r.count for r in records)
        sum_Ay = sum(bar_area(r.dia) * r.count * r.y for r in records)
        sum_Ax = sum(bar_area(r.dia) * r.count * r.x for r in records)
        
        # Transformed area
        A_tr = A_g + (n - 1.0) * As_tot
        
        # Centroid
        cy = (A_g * cy_concrete + (n - 1.0) * sum_Ay) / A_tr
        cx = (n - 1.0) * sum_Ax / A_tr
    else:
        cx, cy = 0.0, cy_concrete
    return cx, cy

def calculate_cracked_inertia(
    geom: SectionGeometry,
    As_bot: float,
    As_top: float,
    d_eff: float | None,
    dp_eff: float | None,
    n: float
) -> float:
    """
    Calculate the cracked transformed moment of inertia (Icr) for rectangular sections.
    Includes both tension and compression steel reinforcement.
    Falls back to Ig for non-rectangular sections or when no bottom reinforcement exists.
    """
    Ig = geom.Ig
    if geom.section_type == "Rectangular" and As_bot > 0:
        d = d_eff if d_eff is not None else (geom.h - geom.cover - geom.stirrup_dia - 25.0)
        dp = dp_eff if dp_eff is not None else (geom.cover + geom.stirrup_dia + 25.0)
        
        # Solving the quadratic equation for cracked neutral axis kd:
        # A_q * kd^2 + B_q * kd + C_q = 0
        A_q = geom.b / 2.0
        B_q = (n - 1.0) * As_top + n * As_bot
        C_q = - (n - 1.0) * As_top * dp - n * As_bot * d
        
        kd = (-B_q + np.sqrt(B_q**2 - 4.0 * A_q * C_q)) / (2.0 * A_q)
        Icr = (geom.b * kd**3 / 3.0) + (n - 1.0) * As_top * (kd - dp)**2 + n * As_bot * (d - kd)**2
        return Icr
    return Ig

