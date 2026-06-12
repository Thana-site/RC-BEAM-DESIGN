"""
RC Section Visualizer — Rebar Models
"""
from dataclasses import dataclass
import pandas as pd

@dataclass
class RebarRecord:
    layer: str       # "Bottom", "Top", "Side", "Custom"
    x: float         # X-coordinate (mm)
    y: float         # Y-coordinate (mm)
    dia: float       # Bar diameter (mm)
    count: int       # Number of bars at this location
    bar_size: str    # Bar designation (e.g. "DB25", "Custom")

    def to_dict(self) -> dict:
        return {
            "Layer": self.layer,
            "X (mm)": self.x,
            "Y (mm)": self.y,
            "Dia (mm)": self.dia,
            "Count": self.count,
            "Bar Size": self.bar_size
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'RebarRecord':
        return cls(
            layer=data.get("Layer", "Custom"),
            x=float(data.get("X (mm)", 0.0)),
            y=float(data.get("Y (mm)", 0.0)),
            dia=float(data.get("Dia (mm)", 0.0)),
            count=int(data.get("Count", 1)),
            bar_size=data.get("Bar Size", "Custom")
        )

def rebar_df_to_records(df: pd.DataFrame) -> list[RebarRecord]:
    """Convert a pandas DataFrame containing rebar data into list of RebarRecord."""
    records = []
    # Drop rows that don't have diameter or count
    df_clean = df.dropna(subset=["Dia (mm)", "Count"])
    for _, row in df_clean.iterrows():
        try:
            records.append(RebarRecord(
                layer=str(row.get("Layer", "Custom")),
                x=float(row.get("X (mm)", 0.0)),
                y=float(row.get("Y (mm)", 0.0)),
                dia=float(row.get("Dia (mm)", 0.0)),
                count=int(row.get("Count", 1)),
                bar_size=str(row.get("Bar Size", "Custom"))
            ))
        except (ValueError, TypeError):
            continue
    return records

def rebar_records_to_df(records: list[RebarRecord]) -> pd.DataFrame:
    """Convert list of RebarRecord back to a pandas DataFrame."""
    if not records:
        return pd.DataFrame(columns=["Layer", "X (mm)", "Y (mm)", "Dia (mm)", "Count", "Bar Size"])
    return pd.DataFrame([r.to_dict() for r in records])
