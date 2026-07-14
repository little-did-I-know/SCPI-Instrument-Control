export type ChannelState = {
  enabled: boolean;
  voltage_scale: number;
  voltage_offset: number;
  coupling: string;
  probe_ratio: number | null;
};

export type TriggerState = {
  mode: string;
  source: string | null;
  level: number | null;
  slope: string | null;
  coupling: string | null;
};

// NOTE: channel keys arrive as strings ("1".."4") — JSON object keys.
export type ScopeState = {
  run_state: string;
  timebase: number;
  channels: Record<string, ChannelState>;
  trigger: TriggerState;
};

export type SessionInfo = {
  id: string;
  label: string;
  mock: boolean;
  address: string | null;
  state: string;
  idn: string;
  model: string;
  dialect: string;
  num_channels: number;
};

export type DiscoveredDevice = {
  address: string;
  idn: string;
  manufacturer: string;
  model: string;
  dialect: string;
  kind: string;
  connected: boolean;
  session_id?: string;
};

export type ModelInfo = {
  model_name: string;
  series: string;
  num_channels: number;
  bandwidth_mhz: number;
  dialect: string;
};

export type MeasurementValue = { channel: number; mtype: string; value: number | null };

export type StreamMessage =
  | { type: "state"; state: ScopeState }
  | { type: "waveform"; channel: number; t0: number; dt: number; points: number[] }
  | { type: "measurements"; values: MeasurementValue[] }
  | { type: "error"; detail: string }
  | { type: "closed" };

export type SessionCreate = { label?: string; address?: string; port?: number; mock?: boolean; model?: string };
export type ChannelPatch = Partial<{ enabled: boolean; voltage_scale: number; voltage_offset: number; coupling: string; probe_ratio: number }>;
export type TriggerPatch = Partial<{ mode: string; source: string; level: number; slope: string; coupling: string }>;
export type RunOp = "run" | "stop" | "single" | "auto";
