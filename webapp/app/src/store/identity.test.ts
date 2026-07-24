import { beforeEach, describe, expect, it } from "vitest";
import { useIdentity } from "./identity";

beforeEach(() => useIdentity.getState().clearIdentity());

describe("identity store", () => {
  it("starts with no identity", () => {
    expect(useIdentity.getState().identity).toBeNull();
  });

  it("setIdentity stores the whoami name", () => {
    useIdentity.getState().setIdentity("robin");
    expect(useIdentity.getState().identity).toBe("robin");
  });

  it("clearIdentity resets to null", () => {
    useIdentity.getState().setIdentity("robin");
    useIdentity.getState().clearIdentity();
    expect(useIdentity.getState().identity).toBeNull();
  });
});
