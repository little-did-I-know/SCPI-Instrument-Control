import type { Kind } from "../features/home/kinds";

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
  kind: Kind;
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
  | { type: "state"; kind: "psu"; outputs: PsuOutputState[] }
  | { type: "state"; kind: "awg"; channels: AwgChannelState[] }
  | { type: "waveform"; channel: number | string; t0: number; dt: number; points: number[] }
  | { type: "measurements"; values: MeasurementValue[]; timestamp?: number }
  | { type: "measurements_config"; items: { channel: number; mtype: string }[] }
  | ({ type: "spectrum" } & SpectrumFrame)
  | ({ type: "reference" } & ReferenceOverlay)
  | ({ type: "reference_stats" } & ReferenceStats)
  | { type: "error"; detail: string }
  | { type: "closed" }
  | ({ type: "log_status" } & LogStatus);

// Every field bar `output` is read through the server's _safe(): a query the
// model does not implement, or a timeout, yields null. `enabled` in particular
// is null-not-false by design — an SPD3303X's CH3 has no status bit and no
// OUTP3?, and rendering an energised rail as a confident "off" is the exact
// safety failure the UI must not commit. null means "unknown"; show it as such.
export type PsuOutputState = {
  output: number;
  voltage: number | null;
  current: number | null;
  enabled: boolean | null;
  measured_voltage: number | null;
  measured_current: number | null;
  measured_power: number | null;
};

export type PsuState = { outputs: PsuOutputState[] };

export type PsuOutputPatch = Partial<{ voltage: number; current: number }>;

// Every field bar `channel` is read through the server's _safe(): a query the
// model does not implement, or a timeout, yields null. `enabled` in particular
// is boolean|null and NEVER defaults to false -- AWGOutput.enabled raises when
// an SDG's OUTPut? response carries no STATE field, and a live output rendered
// as a confident "off" is the dangerous direction. duty_cycle is null unless
// the function is PULSE, and symmetry null unless it is RAMP: the server reads
// each only for the function it belongs to.
export type AwgChannelState = {
  channel: number;
  function: string | null;
  frequency: number | null;
  amplitude: number | null;
  offset: number | null;
  phase: number | null;
  enabled: boolean | null;
  duty_cycle: number | null;
  symmetry: number | null;
};

export type AwgState = { channels: AwgChannelState[] };

export type AwgChannelPatch = Partial<{ function: string; frequency: number; amplitude: number; offset: number; phase: number; duty_cycle: number; symmetry: number }>;

// `kind` is optional and the server defaults it to "scope", so an older client
// that omits it keeps the pre-5.8 behaviour. Sending it is how the UI creates
// anything other than a scope: discovery already knows the kind, and without
// passing it through, clicking Connect on a discovered PSU builds an
// Oscilloscope against a power supply and 409s on the server's kind guard.
export type SessionCreate = { label?: string; kind?: Kind; address?: string; port?: number; mock?: boolean; model?: string };
export type ChannelPatch = Partial<{ enabled: boolean; voltage_scale: number; voltage_offset: number; coupling: string; probe_ratio: number }>;
export type TriggerPatch = Partial<{ mode: string; source: string; level: number; slope: string; coupling: string }>;
export type RunOp = "run" | "stop" | "single" | "auto";
