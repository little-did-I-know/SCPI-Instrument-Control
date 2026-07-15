import { create } from "zustand";
import type { MeasurementValue, ScopeState, SessionInfo } from "../api/types";

export type ConnStatus = "disconnected" | "connecting" | "connected" | "error";

type SessionStore = {
  session: SessionInfo | null;
  scope: ScopeState | null;
  status: ConnStatus;
  error: string | null;
  measurements: MeasurementValue[];
  measurementConfig: { channel: number; mtype: string }[];
  setSession: (session: SessionInfo) => void;
  clearSession: () => void;
  applyState: (state: ScopeState) => void;
  applyMeasurements: (values: MeasurementValue[]) => void;
  applyMeasurementConfig: (items: { channel: number; mtype: string }[]) => void;
  setStatus: (status: ConnStatus) => void;
  setError: (error: string | null) => void;
};

export const useSession = create<SessionStore>((set) => ({
  session: null,
  scope: null,
  status: "disconnected",
  error: null,
  measurements: [],
  measurementConfig: [],
  setSession: (session) => set({ session, status: "connected", error: null }),
  clearSession: () => set({ session: null, scope: null, status: "disconnected", error: null, measurements: [], measurementConfig: [] }),
  applyState: (scope) => set({ scope }),
  applyMeasurements: (measurements) => set({ measurements }),
  applyMeasurementConfig: (measurementConfig) => set({ measurementConfig }),
  setStatus: (status) => set({ status }),
  setError: (error) => set({ error, status: error ? "error" : "connected" }),
}));
