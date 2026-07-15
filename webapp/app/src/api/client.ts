import type { ChannelPatch, DiscoveredDevice, MeasurementValue, ModelInfo, RunOp, ScopeState, SessionCreate, SessionInfo, TriggerPatch } from "./types";

export class ApiError extends Error {
  status: number;
  error: string;
  detail: string;

  constructor(status: number, error: string, detail: string) {
    super(detail || error);
    this.name = "ApiError";
    this.status = status;
    this.error = error;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let error = "Error";
    let detail = "request failed";
    try {
      const body = await response.json();
      error = body.error ?? error;
      detail = body.detail ?? detail;
    } catch {
      // non-JSON error body: keep defaults
    }
    throw new ApiError(response.status, error, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

const scope = (id: string) => `/api/sessions/${id}/scope`;

export const api = {
  models: () => request<ModelInfo[]>("/api/models"),
  discover: (cidr?: string) => request<DiscoveredDevice[]>(cidr ? `/api/discover?cidr=${encodeURIComponent(cidr)}` : "/api/discover"),
  createSession: (body: SessionCreate) => request<SessionInfo>("/api/sessions", json("POST", body)),
  listSessions: () => request<SessionInfo[]>("/api/sessions"),
  getSession: (id: string) => request<SessionInfo>(`/api/sessions/${id}`),
  deleteSession: (id: string) => request<void>(`/api/sessions/${id}`, { method: "DELETE" }),
  getState: (id: string) => request<ScopeState>(`${scope(id)}/state`),
  patchChannel: (id: string, channel: number, body: ChannelPatch) => request<ScopeState>(`${scope(id)}/channels/${channel}`, json("PATCH", body)),
  patchTimebase: (id: string, timebase: number) => request<ScopeState>(`${scope(id)}/timebase`, json("PATCH", { timebase })),
  patchTrigger: (id: string, body: TriggerPatch) => request<ScopeState>(`${scope(id)}/trigger`, json("PATCH", body)),
  runOp: (id: string, op: RunOp) => request<ScopeState>(`${scope(id)}/${op}`, { method: "POST" }),
  command: (id: string, command: string) => request<{ command: string; response: string | null }>(`${scope(id)}/command`, json("POST", { command })),
  setMeasurements: (id: string, items: { channel: number; mtype: string }[]) => request<{ measurements: { channel: number; mtype: string }[] }>(`${scope(id)}/measurements`, json("PUT", items)),
  getMeasurements: (id: string) => request<{ measurements: { channel: number; mtype: string }[] }>(`${scope(id)}/measurements`),
  getMath: (id: string) => request<{ n: number; expression: string; enabled: boolean }[]>(`${scope(id)}/math`),
  patchMath: (id: string, n: number, body: { expression?: string; enabled?: boolean }) => request<{ n: number; expression: string; enabled: boolean }[]>(`${scope(id)}/math/${n}`, json("PATCH", body)),
  captureUrl: (id: string, channels: number[]) => `${scope(id)}/capture.csv?channels=${channels.join(",")}`,
  screenshotUrl: (id: string) => `${scope(id)}/screenshot.png`,
  waveformJsonUrl: (id: string, channels: number[]) => `${scope(id)}/waveform?channels=${channels.join(",")}`,
};

export type { MeasurementValue };
