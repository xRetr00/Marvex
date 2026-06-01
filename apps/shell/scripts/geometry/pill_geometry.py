"""Dynamic Island pill geometry — dev-time calculator.

The agent cannot see the rendered UI, so the pill's dimensions are computed here
once (consistent stadium math, sensible Apple-like proportions) and emitted as a
generated TS constants file via ``emit_constants``. All values are *logical* CSS
pixels; physical sizing/DPI scaling is applied at runtime in the Rust shell
(``set_overlay_size`` multiplies by the monitor scale factor).

Run ``python emit_constants.py`` after changing anything here.
"""

from __future__ import annotations

from dataclasses import dataclass

# Side margin reserved when clamping the expanded pill to a narrow viewport.
DEFAULT_SIDE_MARGIN = 16


@dataclass(frozen=True)
class PillGeometry:
    """Logical-pixel geometry for the idle and expanded pill states."""

    idle_width: int
    idle_height: int
    expanded_max_width: int
    radius_idle: int
    radius_expanded: int
    padding_x: int
    padding_y: int
    shadow_padding: int
    top_margin: int
    anchor: str


def compute_pill_geometry() -> PillGeometry:
    """Compute the canonical pill geometry.

    The idle pill is a true *stadium* (corner radius = half its height). The
    expanded pill is a rounded rectangle that grows downward from the top-center
    notch; the shadow padding is the transparent breathing room the overlay
    window reserves around the pill so its drop shadow is never clipped.
    """

    idle_height = 44
    idle_width = 124
    expanded_max_width = 360
    padding_x = 18
    padding_y = 10

    return PillGeometry(
        idle_width=idle_width,
        idle_height=idle_height,
        expanded_max_width=expanded_max_width,
        # Stadium: a full-height radius gives perfectly round pill ends.
        radius_idle=idle_height // 2,
        # Expanded is taller than a stadium; a softer fixed radius reads better.
        radius_expanded=28,
        padding_x=padding_x,
        padding_y=padding_y,
        # Zero: the native window is clipped exactly to the pill (like the real
        # Dynamic Island, a shadowless cutout). Any padding would expose the
        # window surface around the pill — the "grey/white box" bug.
        shadow_padding=0,
        # Gap below the top edge of the monitor (the "notch" inset).
        top_margin=12,
        anchor="top-center",
    )


def clamp_expanded_width(
    viewport_width: int,
    geo: PillGeometry,
    side_margin: int = DEFAULT_SIDE_MARGIN,
) -> int:
    """Expanded width for a given viewport: full width on roomy screens, bounded
    by the viewport (minus side margins) on cramped ones, so it never overflows
    a small display."""

    return min(geo.expanded_max_width, viewport_width - side_margin * 2)
