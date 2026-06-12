"""
RC Section Visualizer — Rebar Coordinate Auto-Generator
"""
import numpy as np
from models.section import SectionGeometry
from models.rebar import RebarRecord

def generate_rebar_coordinates(
    geom: SectionGeometry,
    layer: str,
    bar_size: str,
    bar_dia: float,
    n_bars: int,
    row_num: int,
    spacing_mode: str,
    fixed_spacing: float
) -> list[RebarRecord]:
    """
    Generate absolute coordinates (x, y) for a group of rebars.
    Returns a list of RebarRecord.
    """
    new_records = []
    
    if geom.section_type == "Circular":
        R_ring = geom.D / 2.0 - geom.cover - geom.stirrup_dia - bar_dia / 2.0
        
        if spacing_mode == "Auto":
            if layer == "Bottom":
                angles = np.linspace(-np.pi + 0.35, -0.35, n_bars).tolist() if n_bars > 1 else [-np.pi/2]
            elif layer == "Top":
                angles = np.linspace(0.35, np.pi - 0.35, n_bars).tolist() if n_bars > 1 else [np.pi/2]
            else: # Side
                angles_left = np.linspace(-np.pi + 0.7, np.pi - 0.7, n_bars).tolist() if n_bars > 1 else [-np.pi]
                angles_right = np.linspace(-0.7, 0.7, n_bars).tolist() if n_bars > 1 else [0.0]
                
                for theta in angles_left:
                    x = R_ring * np.cos(theta)
                    y = R_ring * np.sin(theta)
                    new_records.append(RebarRecord(layer="Side", x=round(x, 1), y=round(y, 1), dia=int(bar_dia), count=1, bar_size=bar_size))
                for theta in angles_right:
                    x = R_ring * np.cos(theta)
                    y = R_ring * np.sin(theta)
                    new_records.append(RebarRecord(layer="Side", x=round(x, 1), y=round(y, 1), dia=int(bar_dia), count=1, bar_size=bar_size))
                return new_records
        else:
            d_theta = fixed_spacing / R_ring
            if layer == "Bottom":
                angles = [-np.pi/2 + (i - (n_bars - 1) / 2.0) * d_theta for i in range(n_bars)]
            elif layer == "Top":
                angles = [np.pi/2 + (i - (n_bars - 1) / 2.0) * d_theta for i in range(n_bars)]
            else: # Side
                angles_left = [np.pi + (i - (n_bars - 1) / 2.0) * d_theta for i in range(n_bars)]
                angles_right = [(i - (n_bars - 1) / 2.0) * d_theta for i in range(n_bars)]
                
                for theta in angles_left:
                    x = R_ring * np.cos(theta)
                    y = R_ring * np.sin(theta)
                    new_records.append(RebarRecord(layer="Side", x=round(x, 1), y=round(y, 1), dia=int(bar_dia), count=1, bar_size=bar_size))
                for theta in angles_right:
                    x = R_ring * np.cos(theta)
                    y = R_ring * np.sin(theta)
                    new_records.append(RebarRecord(layer="Side", x=round(x, 1), y=round(y, 1), dia=int(bar_dia), count=1, bar_size=bar_size))
                return new_records

        for theta in angles:
            x = R_ring * np.cos(theta)
            y = R_ring * np.sin(theta)
            new_records.append(RebarRecord(layer=layer, x=round(x, 1), y=round(y, 1), dia=int(bar_dia), count=1, bar_size=bar_size))
            
        return new_records

    # Rectangular / T-Beam
    _row_gap = max(25.0, bar_dia)
    # For T-Beams, bottom/side bars must be within web width, top bars can span flange
    _effective_b = geom.b_w if (geom.section_type == "T-Beam" and layer != "Top") else geom.b
    _x_min = -_effective_b / 2.0 + geom.cover + geom.stirrup_dia + bar_dia / 2.0
    _x_max =  _effective_b / 2.0 - geom.cover - geom.stirrup_dia - bar_dia / 2.0
    _y_min = -geom.h / 2.0 + geom.cover + geom.stirrup_dia + bar_dia / 2.0
    _y_max =  geom.h / 2.0 - geom.cover - geom.stirrup_dia - bar_dia / 2.0

    if layer == "Bottom":
        y = _y_min + (row_num - 1) * (bar_dia + _row_gap)
        if spacing_mode == "Auto":
            xs = [0.0] if n_bars == 1 else np.linspace(_x_min, _x_max, n_bars).tolist()
        else:
            xs = [-((n_bars - 1) * fixed_spacing) / 2.0 + i * fixed_spacing for i in range(n_bars)]
        for x in xs:
            new_records.append(RebarRecord(layer="Bottom", x=round(x, 1), y=round(y, 1), dia=int(bar_dia), count=1, bar_size=bar_size))
            
    elif layer == "Top":
        y = _y_max - (row_num - 1) * (bar_dia + _row_gap)
        if spacing_mode == "Auto":
            xs = [0.0] if n_bars == 1 else np.linspace(_x_min, _x_max, n_bars).tolist()
        else:
            xs = [-((n_bars - 1) * fixed_spacing) / 2.0 + i * fixed_spacing for i in range(n_bars)]
        for x in xs:
            new_records.append(RebarRecord(layer="Top", x=round(x, 1), y=round(y, 1), dia=int(bar_dia), count=1, bar_size=bar_size))
            
    elif layer == "Side":
        x_l = -_effective_b / 2.0 + geom.cover + geom.stirrup_dia + bar_dia / 2.0
        x_r =  _effective_b / 2.0 - geom.cover - geom.stirrup_dia - bar_dia / 2.0
        if spacing_mode == "Auto":
            ys = [0.0] if n_bars == 1 else np.linspace(_y_min, _y_max, n_bars).tolist()
        else:
            ys = [-((n_bars - 1) * fixed_spacing) / 2.0 + i * fixed_spacing for i in range(n_bars)]
        for y in ys:
            new_records.append(RebarRecord(layer="Side", x=round(x_l, 1), y=round(y, 1), dia=int(bar_dia), count=1, bar_size=bar_size))
            new_records.append(RebarRecord(layer="Side", x=round(x_r, 1), y=round(y, 1), dia=int(bar_dia), count=1, bar_size=bar_size))
            
    return new_records

def get_row_preview_y(geom: SectionGeometry, layer: str, bar_dia: float, row_num: int) -> float:
    """Return the Y coordinate preview for Bottom or Top layer row generation."""
    if geom.section_type == "Circular":
        R_ring = geom.D / 2.0 - geom.cover - geom.stirrup_dia - bar_dia / 2.0
        if layer == "Bottom":
            return round(-R_ring, 1)
        elif layer == "Top":
            return round(R_ring, 1)
        return 0.0
        
    _row_gap = max(25.0, bar_dia)
    if layer == "Bottom":
        return round(-geom.h / 2.0 + geom.cover + geom.stirrup_dia + bar_dia / 2.0 + (row_num - 1) * (bar_dia + _row_gap), 1)
    elif layer == "Top":
        return round(geom.h / 2.0 - geom.cover - geom.stirrup_dia - bar_dia / 2.0 - (row_num - 1) * (bar_dia + _row_gap), 1)
    return 0.0
