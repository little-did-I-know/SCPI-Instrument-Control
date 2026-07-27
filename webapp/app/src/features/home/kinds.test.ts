import { describe, expect, it } from "vitest";
import { KIND_META, KIND_ORDER, kindMeta } from "./kinds";

describe("kinds", () => {
  it("marks scope, psu, and awg connectable, daq/unknown not yet", () => {
    expect(KIND_META.scope.connectable).toBe(true);
    expect(KIND_META.psu.connectable).toBe(true);
    expect(KIND_META.awg.connectable).toBe(true);
    expect(KIND_META.daq.connectable).toBe(false);
    expect(KIND_META.unknown.connectable).toBe(false);
  });

  it("orders scope first, unknown last", () => {
    expect(KIND_ORDER[0]).toBe("scope");
    expect(KIND_ORDER[KIND_ORDER.length - 1]).toBe("unknown");
  });

  it("kindMeta falls back to unknown for an unrecognized kind", () => {
    expect(kindMeta("frobnicator")).toBe(KIND_META.unknown);
    expect(kindMeta("scope").label).toBe(KIND_META.scope.label);
  });
});
