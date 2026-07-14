import { describe, expect, it } from "vitest";
import { deviceKey } from "./deviceKey";

describe("deviceKey", () => {
  it("prefers session_id (two mock sessions stay distinct)", () => {
    const a = deviceKey({ session_id: "s1", address: null, model: "Mock" });
    const b = deviceKey({ session_id: "s2", address: null, model: "Mock" });
    expect(a).toBe("s1");
    expect(b).toBe("s2");
    expect(a).not.toBe(b);
  });

  it("falls back to address when there is no session", () => {
    expect(deviceKey({ address: "192.168.1.50", model: "SDS824X HD" })).toBe("192.168.1.50");
  });

  it("falls back to model when address is null and there is no session", () => {
    expect(deviceKey({ address: null, model: "Mock" })).toBe("Mock");
  });
});
