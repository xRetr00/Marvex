import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DynamicIsland from ".";

describe("DynamicIsland", () => {
  it("renders the pill as the root visual element without an outer card wrapper", () => {
    const { container } = render(<DynamicIsland view="idle" idleContent={<span>Idle</span>} />);

    const pill = screen.getByText("Idle").closest(".marvex-dynamic-island-pill");
    expect(pill).toBe(container.firstElementChild);
  });
});
