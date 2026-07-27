import { create } from "zustand";
import type { LogStatus, MeasurementValue, PsuState, ReferenceStats, ScopeState, SessionInfo } from "../api/types";

export type ConnStatus = "disconnected" | "connecting" | "connected" | "error";

type SessionStore = {
  session: SessionInfo | null;
  scope: ScopeState | null;
  psu: PsuState | null;
  status: ConnStatus;
  error: string | null;
  measurements: MeasurementValue[];
  measurementConfig: { channel: number; mtype: string }[];
  activeReference: { name: string; channel: number | null } | null;
  referenceStats: ReferenceStats | null;
  logStatus: LogStatus | null;
  setSession: (session: SessionInfo) => void;
  clearSession: () => void;
  applyState: (state: ScopeState) => void;
  applyPsuState: (state: PsuState) => void;
  applyMeasurements: (values: MeasurementValue[]) => void;
  applyMeasurementConfig: (items: { channel: number; mtype: string }[]) => void;
  applyReference: (ref: { name: string; channel: number | null } | null) => void;
  applyReferenceStats: (stats: ReferenceStats | null) => void;
  applyLogStatus: (status: LogStatus | null) => void;
  setStatus: (status: ConnStatus) => void;
  setError: (error: string | null) => void;
};

export const useSession = create<SessionStore>((set) => ({
  session: null,
  scope: null,
  psu: null,
  status: "disconnected",
  error: null,
  measurements: [],
  measurementConfig: [],
  activeReference: null,
  referenceStats: null,
  logStatus: null,
  // Both kind-specific slices are cleared: switching sessions must not leave
  // the previous instrument's readings on screen while the new one's first
  // frame is still in flight — and with two kinds, a psu→psu switch would
  // otherwise show the old supply's outputs under the new supply's name.
  setSession: (session) => set({ session, scope: null, psu: null, status: "connected", error: null }),
  clearSession: () => set({ session: null, scope: null, psu: null, status: "disconnected", error: null, measurements: [], measurementConfig: [], activeReference: null, referenceStats: null, logStatus: null }),
  applyState: (scope) => set({ scope }),
  applyPsuState: (psu) => set({ psu }),
  applyMeasurements: (measurements) => set({ measurements }),
  applyMeasurementConfig: (measurementConfig) => set({ measurementConfig }),
  applyReference: (activeReference) => set({ activeReference }),
  applyReferenceStats: (referenceStats) => set({ referenceStats }),
  applyLogStatus: (logStatus) => set({ logStatus }),
  setStatus: (status) => set({ status }),
  setError: (error) => set({ error, status: error ? "error" : "connected" }),
}));
