"""
RC Section Visualizer — Validation Calculations
"""
import numpy as np
from models.section import SectionGeometry
from models.rebar import RebarRecord

def check_bars_outside_bounds(geom: SectionGeometry, records: list[RebarRecord]) -> int:
    """
    Check if any rebar is outside the section geometry boundary.
    Returns the count of out-of-boundary bars.
    """
    outside_count = 0
    h_limit = geom.h / 2.0
    
    for r in records:
        if geom.section_type == "Rectangular":
            b_limit = geom.b / 2.0
            if (abs(r.x) + r.dia / 2.0) > b_limit or (abs(r.y) + r.dia / 2.0) > h_limit:
                outside_count += 1
        elif geom.section_type == "T-Beam":
            # Flange is from y = h/2 - t_f to y = h/2
            y_flange_bottom = geom.h / 2.0 - geom.t_f
            if r.y < y_flange_bottom:
                b_limit = geom.b_w / 2.0
            else:
                b_limit = geom.b_f / 2.0
            if (abs(r.x) + r.dia / 2.0) > b_limit or (abs(r.y) + r.dia / 2.0) > h_limit:
                outside_count += 1
        elif geom.section_type == "Circular":
            # Check radial distance
            dist = np.sqrt(r.x**2 + r.y**2)
            if (dist + r.dia / 2.0) > (geom.D / 2.0):
                outside_count += 1
                
    return outside_count
