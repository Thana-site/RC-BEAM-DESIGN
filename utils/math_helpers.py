"""
RC Section Visualizer — Mathematics Helpers
"""
import numpy as np

def bar_area(d: float) -> float:
    """Return total steel area (mm²) for a given bar diameter (mm)."""
    return np.pi * d**2 / 4.0
