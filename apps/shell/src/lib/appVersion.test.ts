import { describe, expect, it } from "vitest";
import { MARVEX_APP_VERSION } from "./appVersion";

describe("MARVEX_APP_VERSION", () => {
  it("comes from the central build-time version", () => {
    expect(MARVEX_APP_VERSION).toBe("0.2.1");
  });
});
