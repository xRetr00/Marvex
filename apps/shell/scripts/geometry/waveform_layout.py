"""Waveform canvas layout — dev-time calculator.

The waveform GLSL shader (``MarvexWaveform``) normalises by ``min(resolution)``,
so the canvas aspect ratio matters for how the bands read. This computes the
canvas dimensions for the compact pill (small, beside the status dot) and the
expanded pill (wide), derived from the pill geometry so they always fit.
"""

from __future__ import annotations

from dataclasses import dataclass

from pill_geometry import PillGeometry

# Horizontal room reserved in the idle pill for the pulsing status dot + gap.
COMPACT_DOT_ALLOWANCE = 24


@dataclass(frozen=True)
class WaveformBox:
    width: int
    height: int


@dataclass(frozen=True)
class WaveformLayout:
    compact: WaveformBox
    expanded: WaveformBox


def _even(value: int) -> int:
    """Round down to a multiple of 4 so the shader's band math lands cleanly."""

    return max(4, (value // 4) * 4)


def compute_waveform_layout(geo: PillGeometry) -> WaveformLayout:
    content_width = geo.idle_width - 2 * geo.padding_x
    content_height = geo.idle_height - 2 * geo.padding_y

    compact = WaveformBox(
        width=_even(content_width - COMPACT_DOT_ALLOWANCE),
        height=content_height,
    )

    expanded_width = _even(geo.expanded_max_width - 2 * geo.padding_x)
    expanded = WaveformBox(
        width=expanded_width,
        # ~4:1 reads as a lively full-width waveform without dominating the pill.
        height=_even(expanded_width // 4),
    )

    return WaveformLayout(compact=compact, expanded=expanded)
