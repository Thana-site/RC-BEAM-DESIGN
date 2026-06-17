"""Automatic label placement with collision avoidance for Plotly diagrams."""

from dataclasses import dataclass

MIN_H_SPACING_PX = 25
MIN_V_SPACING_PX = 18


@dataclass
class SubplotLayout:
    """Approximate data-to-pixel mapping for one subplot."""

    x_range: tuple[float, float]
    y_range: tuple[float, float]
    width_px: float = 300.0
    height_px: float = 400.0
    margin_left_px: float = 8.0
    margin_top_px: float = 46.0

    def anchor_to_px(self, anchor_x: float, anchor_y: float) -> tuple[float, float]:
        x0, x1 = self.x_range
        y0, y1 = self.y_range
        x_frac = (anchor_x - x0) / (x1 - x0) if x1 != x0 else 0.5
        y_frac = (y0 - anchor_y) / (y0 - y1) if y0 != y1 else 0.5
        return (
            self.margin_left_px + x_frac * self.width_px,
            self.margin_top_px + y_frac * self.height_px,
        )


@dataclass
class DiagramLabel:
    text: str
    anchor_x: float
    anchor_y: float
    priority: int
    color: str
    row: int = 1
    col: int = 1
    size: int = 9
    xanchor: str = "left"
    yanchor: str = "middle"
    preferred_xshift: int = 8
    preferred_yshift: int = 0
    xshift: int = 0
    yshift: int = 0
    ax: int = 0
    ay: int = 0
    showarrow: bool = False
    visible: bool = True
    always_show_arrow: bool = False

    def plain_text(self) -> str:
        # FIX 1: Handle Unicode ε (previously &epsilon; HTML entity was replaced)
        return (
            self.text.replace("ε", "e")  # Unicode epsilon → plain 'e' for width estimate
            .replace("&epsilon;", "e")    # legacy HTML entity fallback
            .replace("<br>", " ")
            .replace("<sup>", "")
            .replace("</sup>", "")
        )


class LabelPlacer:
    """Place diagram labels without pixel-space overlap."""

    def __init__(self, layout: SubplotLayout) -> None:
        self._layout = layout
        self._placed: list[tuple[tuple[float, float, float, float], int]] = []

    def _text_bbox_px(self, label: DiagramLabel) -> tuple[float, float, float, float]:
        anchor_px_x, anchor_px_y = self._layout.anchor_to_px(label.anchor_x, label.anchor_y)
        plain = label.plain_text()
        char_w = label.size * 0.62
        line_h = label.size + 5
        width = max(len(plain), 1) * char_w + 6
        height = line_h + 4

        if label.showarrow:
            off_x, off_y = label.ax, label.ay
        else:
            off_x, off_y = label.xshift, label.yshift

        if label.xanchor == "left":
            left = anchor_px_x + off_x
        elif label.xanchor == "right":
            left = anchor_px_x + off_x - width
        else:
            left = anchor_px_x + off_x - width / 2

        if label.yanchor == "top":
            top = anchor_px_y + off_y
        elif label.yanchor == "bottom":
            top = anchor_px_y + off_y - height
        else:
            top = anchor_px_y + off_y - height / 2

        return (left, top, left + width, top + height)

    def _overlaps(self, bbox: tuple[float, float, float, float]) -> bool:
        for existing, _ in self._placed:
            if not (
                bbox[2] + MIN_H_SPACING_PX < existing[0]
                or existing[2] + MIN_H_SPACING_PX < bbox[0]
                or bbox[3] + MIN_V_SPACING_PX < existing[1]
                or existing[3] + MIN_V_SPACING_PX < bbox[1]
            ):
                return True
        return False

    def _candidate_offsets(self, label: DiagramLabel) -> list[tuple[int, int, bool]]:
        px = label.preferred_xshift
        py = label.preferred_yshift
        candidates: list[tuple[int, int, bool]] = []
        y_deltas = [0, 16, -16, 32, -32, 48, -48, 64, -64]
        x_deltas = [0, 22, 44, -22, -44, 66, -66, 88, -88]

        for dy in y_deltas:
            for dx in x_deltas:
                use_arrow = abs(dx) >= 18 or abs(dy) >= 18
                candidates.append((px + dx, py + dy, use_arrow))
        return candidates

    def place(self, label: DiagramLabel) -> DiagramLabel:
        if label.always_show_arrow:
            label.showarrow = True
            label.ax = label.preferred_xshift
            label.ay = label.preferred_yshift
            label.xshift = 0
            label.yshift = 0
            label.visible = True
            self._placed.append((self._text_bbox_px(label), label.priority))
            return label

        for x_off, y_off, use_arrow in self._candidate_offsets(label):
            label.showarrow = use_arrow
            if use_arrow:
                label.ax = x_off
                label.ay = y_off
                label.xshift = 0
                label.yshift = 0
            else:
                label.xshift = x_off
                label.yshift = y_off
                label.ax = 0
                label.ay = 0

            if not self._overlaps(self._text_bbox_px(label)):
                label.visible = True
                self._placed.append((self._text_bbox_px(label), label.priority))
                return label

        if label.priority < 70:
            label.visible = False
            return label

        label.showarrow = True
        label.ax = label.preferred_xshift + 52
        label.ay = label.preferred_yshift + 32
        label.xshift = 0
        label.yshift = 0
        label.visible = True
        self._placed.append((self._text_bbox_px(label), label.priority))
        return label

    def place_all(self, labels: list[DiagramLabel]) -> list[DiagramLabel]:
        ordered = sorted(labels, key=lambda item: item.priority, reverse=True)
        for label in ordered:
            self.place(label)
        return labels

    def apply_to_figure(self, fig, labels: list[DiagramLabel]) -> None:
        for label in labels:
            if not label.visible:
                continue
            kwargs: dict = {
                "x": label.anchor_x,
                "y": label.anchor_y,
                "text": label.text,
                "showarrow": label.showarrow,
                "font": dict(color=label.color, size=label.size),
                "xanchor": label.xanchor,
                "yanchor": label.yanchor,
                "row": label.row,
                "col": label.col,
            }
            if label.showarrow:
                kwargs.update(
                    ax=label.ax,
                    ay=label.ay,
                    arrowhead=2,
                    arrowsize=0.8,
                    arrowwidth=1,
                    arrowcolor=label.color,
                )
            else:
                kwargs.update(xshift=label.xshift, yshift=label.yshift)
            fig.add_annotation(**kwargs)
