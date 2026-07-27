import { describe, expect, it } from "vitest";
import { KIND_VIEWS } from "./kindViews";

// The registry is the ONLY mapping from an instrument kind to a view. Adding a
// kind must mean adding an entry here -- not another branch in App.tsx, which
// is what this whole sub-project exists to remove.
describe("KIND_VIEWS", () => {
  it("registers a body for every kind it claims to support", () => {
    for (const [kind, view] of Object.entries(KIND_VIEWS)) {
      expect(view, `${kind} has no view`).toBeDefined();
      expect(typeof view!.body, `${kind} has no body component`).toBe("function");
    }
  });

  it("covers the kinds the gateway can connect to today", () => {
    expect(Object.keys(KIND_VIEWS).sort()).toEqual(["psu", "scope"]);
  });

  it("does not register a kind the gateway cannot connect to yet", () => {
    expect(KIND_VIEWS.awg).toBeUndefined();
    expect(KIND_VIEWS.daq).toBeUndefined();
  });
});
