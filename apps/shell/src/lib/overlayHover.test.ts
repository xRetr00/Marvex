import { describe, expect, it, vi } from "vitest";
import { makeHoverEdgeTrigger } from "./overlayHover";

describe("makeHoverEdgeTrigger", () => {
  it("only fires when the over state changes", () => {
    const onChange = vi.fn();
    const trigger = makeHoverEdgeTrigger(onChange);
    trigger(false); // initial known state may emit once
    onChange.mockClear();
    trigger(false);
    trigger(false);
    expect(onChange).not.toHaveBeenCalled();
    trigger(true);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith(true);
    trigger(true);
    expect(onChange).toHaveBeenCalledTimes(1);
    trigger(false);
    expect(onChange).toHaveBeenCalledTimes(2);
    expect(onChange).toHaveBeenLastCalledWith(false);
  });
});
