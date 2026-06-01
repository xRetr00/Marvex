"""Tests for the dev-time Dynamic Island geometry helpers.

These scripts compute the pill/waveform geometry the agent cannot eyeball, and
emit a generated TS constants file (+ a Rust constants block). The math must be
internally consistent (stadium radius, content boxes fit, viewport clamping) so
the emitted constants are trustworthy.
"""

from __future__ import annotations

import pathlib
import sys

GEO_DIR = pathlib.Path(__file__).resolve().parents[2] / "apps" / "shell" / "scripts" / "geometry"
sys.path.insert(0, str(GEO_DIR))

import emit_constants  # noqa: E402
import pill_geometry  # noqa: E402
import waveform_layout  # noqa: E402


def test_idle_pill_is_a_stadium_wider_than_tall() -> None:
    geo = pill_geometry.compute_pill_geometry()
    # A stadium's corner radius is exactly half its height.
    assert geo.radius_idle == geo.idle_height // 2
    # The compact pill reads as a horizontal pill, not a circle/tall box.
    assert geo.idle_width > geo.idle_height


def test_expanded_is_larger_and_anchored_top_center() -> None:
    geo = pill_geometry.compute_pill_geometry()
    assert geo.expanded_max_width > geo.idle_width
    assert geo.anchor == "top-center"
    # Zero shadow padding: the window is clipped exactly to the pill.
    assert geo.shadow_padding >= 0
    assert geo.top_margin >= 0


def test_expanded_width_clamps_to_viewport() -> None:
    geo = pill_geometry.compute_pill_geometry()
    # Roomy screen → full expanded width.
    assert pill_geometry.clamp_expanded_width(1920, geo) == geo.expanded_max_width
    # Cramped screen → bounded by the viewport minus side margins.
    narrow = pill_geometry.clamp_expanded_width(200, geo)
    assert narrow < geo.expanded_max_width
    assert narrow <= 200


def test_waveform_boxes_fit_inside_their_pills() -> None:
    geo = pill_geometry.compute_pill_geometry()
    wf = waveform_layout.compute_waveform_layout(geo)
    # Compact waveform fits inside the idle pill's content box.
    assert wf.compact.width <= geo.idle_width - 2 * geo.padding_x
    assert wf.compact.height <= geo.idle_height - 2 * geo.padding_y
    # Expanded waveform fits inside the expanded pill width.
    assert wf.expanded.width <= geo.expanded_max_width - 2 * geo.padding_x
    # Expanding gives the waveform more room than the compact pill.
    assert wf.expanded.width > wf.compact.width


def test_emitted_ts_declares_the_constants_object() -> None:
    geo = pill_geometry.compute_pill_geometry()
    wf = waveform_layout.compute_waveform_layout(geo)
    ts = emit_constants.render_ts(geo, wf)
    assert "export const ISLAND_GEOMETRY" in ts
    assert "DO NOT EDIT" in ts
    assert str(geo.expanded_max_width) in ts
    assert '"top-center"' in ts or "'top-center'" in ts


def test_emitted_rust_declares_anchor_constants() -> None:
    geo = pill_geometry.compute_pill_geometry()
    rust = emit_constants.render_rust(geo)
    assert "OVERLAY_TOP_MARGIN" in rust
    assert "OVERLAY_SHADOW_PADDING" in rust
    assert str(geo.top_margin) in rust
