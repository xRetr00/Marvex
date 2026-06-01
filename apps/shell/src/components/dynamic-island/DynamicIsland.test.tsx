import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DynamicIsland from "./DynamicIsland";
import { ISLAND_GEOMETRY } from "./geometry.generated";

describe("DynamicIsland morph pill", () => {
  it("renders idle content and not expanded content when view=idle", () => {
    render(
      <DynamicIsland
        view="idle"
        idleContent={<span>IDLE</span>}
        expandedContent={<span>EXPANDED</span>}
      />,
    );
    expect(screen.getByText("IDLE")).toBeInTheDocument();
    expect(screen.queryByText("EXPANDED")).not.toBeInTheDocument();
  });

  it("renders expanded content when view=expanded", () => {
    render(
      <DynamicIsland
        view="expanded"
        idleContent={<span>IDLE</span>}
        expandedContent={<span>EXPANDED</span>}
      />,
    );
    expect(screen.getByText("EXPANDED")).toBeInTheDocument();
  });

  it("is the root pill element and uses the generated corner radius per state", () => {
    const { container } = render(
      <DynamicIsland view="expanded" expandedContent={<span>EXPANDED</span>} />,
    );
    const pill = container.querySelector(".marvex-island-pill");
    expect(pill).toBe(container.firstElementChild);
    expect(pill).toHaveStyle({ borderRadius: `${ISLAND_GEOMETRY.expanded.radius}px` });
  });

  it("grows downward from the top (transform-origin anchored to top)", () => {
    const { container } = render(
      <DynamicIsland view="idle" idleContent={<span>IDLE</span>} />,
    );
    const pill = container.querySelector(".marvex-island-pill") as HTMLElement;
    expect(pill.style.transformOrigin).toContain("top");
  });
});
