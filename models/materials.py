"""
RC Section Visualizer — Material Models
"""
from dataclasses import dataclass
import numpy as np
from constants import KSC_TO_MPA, MPA_TO_KSC

@dataclass
class ConcreteProps:
    fc_ksc: float
    
    @property
    def fc_prime(self) -> float:
        """Concrete compressive strength in MPa."""
        return self.fc_ksc * KSC_TO_MPA

    @property
    def Ec_mpa(self) -> float:
        """Modulus of elasticity in MPa: 4700 * sqrt(f'c)."""
        return 4700.0 * np.sqrt(self.fc_prime)

    @property
    def Ec_ksc(self) -> float:
        """Modulus of elasticity in ksc."""
        return self.Ec_mpa * MPA_TO_KSC

    @property
    def beta1(self) -> float:
        """Stress-block factor (ACI 318-19 Sec 22.2.2.4)."""
        fc = self.fc_ksc
        if fc <= 280:
            return 0.85
        elif fc <= 550:
            return 0.85 - 0.05 * (fc - 280) / 70
        else:
            return 0.65



@dataclass
class SteelProps:
    fy_ksc: float
    fyt_ksc: float
    Es_mpa: float = 200000.0  # MPa - standard elastic modulus of steel

    @property
    def fy(self) -> float:
        """Longitudinal steel yield strength in MPa."""
        return self.fy_ksc * KSC_TO_MPA

    @property
    def fyt(self) -> float:
        """Stirrup steel yield strength in MPa."""
        return self.fyt_ksc * KSC_TO_MPA

    @property
    def Es_ksc(self) -> float:
        """Modulus of elasticity of steel in ksc."""
        return self.Es_mpa * MPA_TO_KSC

