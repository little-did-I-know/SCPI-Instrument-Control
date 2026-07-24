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
  viewers: number;
  owner: string;
};

export type DiscoveredDevice = {
  address: string | null;
  idn: string;
  manufacturer: string;
  model: string;
  dialect: string;
  kind: string;
  connected: boolean;
  session_id?: string;
  viewers?: number;
};

export type ModelInfo = {
  model_name: string;
  series: string;
  num_channels: number;
  bandwidth_mhz: number;
  dialect: string;
};

export type MeasurementValue = { channel: number; mtype: string; value: number | null };

export type SpectrumConfig = { enabled: boolean; channel: number; window: string; db: boolean };
export type FilterConfig = { n: number; source: number; kind: "lowpass" | "highpass" | "bandpass"; cutoff_low: number | null; cutoff_high: number | null; order: number; enabled: boolean };
export type ReferenceInfo = { name: string; channel: number | null; timestamp: string; num_samples: number; time_span: number };
export type ReferenceOverlay = { name: string | null; channel: number | null; t0: number; dt: number; points: number[] };
export type ReferenceStats = { correlation: number | null; max_deviation: number | null };
export type SpectrumFrame = { channel: number; f0: number; df: number; points: number[]; db: boolean; window: string; peaks: [number, number][]; thd: number | null };

export type LogStatus = { state: "idle" | "recording"; started_at: number | null; row_count: number; columns: { channel: number; mtype: string }[] };
export type LogInfo = LogStatus & { max_rows: number };
export type LogData = { columns: { channel: number; mtype: string }[]; rows: (number | null)[][] };

export type StreamMessage =
  | { type: "state"; state: ScopeState }
  | { type: "waveform"; channel: number | string; t0: number; dt: number; points: number[] }
  | { type: "measurements"; values: MeasurementValue[]; timestamp?: number }
  | { type: "measurements_config"; items: { channel: number; mtype: string }[] }
  | ({ type: "spectrum" } & SpectrumFrame)
  | ({ type: "reference" } & ReferenceOverlay)
  | ({ type: "reference_stats" } & ReferenceStats)
  | { type: "error"; detail: string }
  | { type: "closed" }
  | ({ type: "log_status" } & LogStatus);

export type SessionCreate = { label?: string; address?: string; port?: number; mock?: boolean; model?: string };
export type ChannelPatch = Partial<{ enabled: boolean; voltage_scale: number; voltage_offset: number; coupling: string; probe_ratio: number }>;
export type TriggerPatch = Partial<{ mode: string; source: string; level: number; slope: string; coupling: string }>;
export type RunOp = "run" | "stop" | "single" | "auto";
