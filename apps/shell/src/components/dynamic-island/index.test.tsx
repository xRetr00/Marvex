import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DynamicIsland from ".";

describe("DynamicIsland", () => {
  it("renders the pill as the root visual element without an outer card wrapper", () => {
    const { container } = render(<DynamicIsland view="idle" idleContent={<span>Idle</span>} />);

    const pill = screen.getByText("Idle").closest(".marvex-dynamic-island-pill");
    expect(pill).toBe(container.firstElementChild);
  });

  it("uses the pretty-toast dynamic island pill geometry", () => {
    const { container } = render(<DynamicIsland view="idle" idleContent={<span>Idle</span>} />);

    const pill = container.querySelector(".marvex-dynamic-island-pill");
    expect(pill).toHaveStyle({
      background: "#000",
      borderRadius: "30px",
      padding: "14px 20px",
      width: "min(360px, calc(100vw - 20px))",
    });
  });

  it("allows an explicit compact width for the native overlay bootstrap window", () => {
    const { container } = render(<DynamicIsland view="idle" idleContent={<span>Idle</span>} width={124} />);

    const pill = container.querySelector(".marvex-dynamic-island-pill");
    expect(pill).toHaveStyle({
      width: "124px",
      minWidth: "124px",
    });
  });
});
