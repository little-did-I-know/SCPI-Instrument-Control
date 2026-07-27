import { describe, expect, it } from "vitest";
import { KIND_META } from "../home/kinds";
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

  it("registers a view for every kind the home screen offers to connect", () => {
    // Derived rather than a hardcoded key list: a kind flipped to
    // connectable:true without a registry entry puts a Connect button on the
    // home screen that lands the user on "coming soon". That is the failure
    // worth guarding, and it survives the next kind being added.
    const connectable = Object.entries(KIND_META)
      .filter(([, meta]) => meta.connectable)
      .map(([kind]) => kind)
      .sort();
    expect(Object.keys(KIND_VIEWS).sort()).toEqual(connectable);
  });
});
