import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { IslandWaveform } from "./IslandWaveform";
import { ISLAND_GEOMETRY } from "./geometry.generated";

describe("IslandWaveform", () => {
  it("uses the compact waveform canvas dimensions inside the idle pill", () => {
    const { container } = render(<IslandWaveform variant="compact" audioLevel={0.2} />);
    const canvas = container.querySelector("canvas");
    expect(canvas).toHaveAttribute("width", String(ISLAND_GEOMETRY.waveform.compact.width));
    expect(canvas).toHaveAttribute("height", String(ISLAND_GEOMETRY.waveform.compact.height));
  });

  it("uses the expanded waveform canvas dimensions when expanded", () => {
    const { container } = render(<IslandWaveform variant="expanded" audioLevel={0.5} />);
    const canvas = container.querySelector("canvas");
    expect(canvas).toHaveAttribute("width", String(ISLAND_GEOMETRY.waveform.expanded.width));
    expect(canvas).toHaveAttribute("height", String(ISLAND_GEOMETRY.waveform.expanded.height));
  });
});
