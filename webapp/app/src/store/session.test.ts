import { beforeEach, describe, expect, it } from "vitest";
import { useSession } from "./session";
import type { ScopeState, SessionInfo } from "../api/types";

const SESSION: SessionInfo = { id: "abc", label: "bench", mock: false, address: "192.168.1.50", state: "connected", idn: "Siglent,SDS824X HD,1,1", model: "SDS824X HD", dialect: "modern", num_channels: 4 };

const STATE: ScopeState = {
  run_state: "STOP",
  timebase: 0.001,
  channels: { "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: 10 } },
  trigger: { mode: "AUTO", source: "C1", level: 0.5, slope: "POS", coupling: "DC" },
};

beforeEach(() => useSession.getState().clearSession());

describe("session store", () => {
  it("starts empty and disconnected", () => {
    const s = useSession.getState();
    expect(s.session).toBeNull();
    expect(s.scope).toBeNull();
    expect(s.status).toBe("disconnected");
  });

  it("applyState replaces the scope snapshot", () => {
    useSession.getState().setSession(SESSION);
    useSession.getState().applyState(STATE);
    expect(useSession.getState().scope?.timebase).toBe(0.001);
    expect(useSession.getState().scope?.channels["1"].enabled).toBe(true);
    useSession.getState().applyState({ ...STATE, timebase: 0.002 });
    expect(useSession.getState().scope?.timebase).toBe(0.002);
  });

  it("tolerates null trigger fields (legacy/modern degrade)", () => {
    useSession.getState().applyState({ ...STATE, trigger: { mode: "AUTO", source: null, level: null, slope: null, coupling: null } });
    expect(useSession.getState().scope?.trigger.level).toBeNull();
  });

  it("clearSession resets everything", () => {
    useSession.getState().setSession(SESSION);
    useSession.getState().applyState(STATE);
    useSession.getState().applyMeasurements([{ channel: 1, mtype: "PKPK", value: 2 }]);
    useSession.getState().clearSession();
    const s = useSession.getState();
    expect(s.session).toBeNull();
    expect(s.scope).toBeNull();
    expect(s.measurements).toEqual([]);
    expect(s.status).toBe("disconnected");
  });

  it("applyMeasurements stores nulls as-is", () => {
    useSession.getState().applyMeasurements([{ channel: 1, mtype: "FREQ", value: null }]);
    expect(useSession.getState().measurements[0].value).toBeNull();
  });
});
