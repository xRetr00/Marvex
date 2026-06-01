import { describe, expect, it, vi } from "vitest";
import { toOverlayWindowSize } from "./overlay";
import { ISLAND_GEOMETRY } from "@/components/dynamic-island/geometry.generated";

vi.mock("../lib/tauriBridge", () => ({ listen: vi.fn(async () => vi.fn()) }));
vi.mock("../lib/shellCommands", () => ({ setOverlaySize: vi.fn(), showChat: vi.fn() }));
vi.mock("../lib/controlPlaneClient", () => ({
  fetchPendingApprovals: vi.fn(async () => []),
}));

describe("overlay sizing", () => {
  it("adds the geometry shadow padding so the native rounded window does not clip the pill", () => {
    const pad = ISLAND_GEOMETRY.shadowPadding;
    expect(toOverlayWindowSize({ width: 128.2, height: 42.1 })).toEqual({
      width: 128 + pad * 2,
      height: 42 + pad * 2,
    });
  });
});
