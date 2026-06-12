"""
RC Section Visualizer — Section Geometry Models
"""
from dataclasses import dataclass

@dataclass
class SectionGeometry:
    section_type: str  # "Rectangular"
    b: float           # Effective width (mm)
    h: float           # Overall depth (mm)
    cover: float       # Clear cover to stirrups (mm)
    stirrup_dia: float # Stirrup diameter (mm)
    D: float = 0.0
    b_f: float = 0.0
    t_f: float = 0.0
    b_w: float = 0.0

    @property
    def Ag(self) -> float:
        """Gross area (mm²)."""
        return self.b * self.h

    @property
    def Ig(self) -> float:
        """Gross moment of inertia (mm⁴) about the centroidal axis."""
        return self.b * self.h**3 / 12.0
