export type Kind = "scope" | "psu" | "awg" | "daq" | "unknown";

export type KindMeta = {
  label: string;
  plural: string;
  accent: string; // CSS color / token
  connectable: boolean;
};

// The single extension point for new instrument kinds (spec: future scientific
// device types slot in here + a discovery classifier + a post-connect view).
export const KIND_META: Record<Kind, KindMeta> = {
  scope: { label: "Oscilloscope", plural: "Oscilloscopes", accent: "var(--ch1)", connectable: true },
  psu: { label: "Power supply", plural: "Power supplies", accent: "var(--ch2)", connectable: true },
  awg: { label: "AWG", plural: "AWGs", accent: "var(--warning)", connectable: true },
  daq: { label: "DAQ", plural: "DAQ", accent: "var(--ch3)", connectable: false },
  unknown: { label: "Unknown", plural: "Unknown", accent: "var(--text-muted)", connectable: false },
};

export const KIND_ORDER: Kind[] = ["scope", "psu", "awg", "daq", "unknown"];

export function kindMeta(kind: string): KindMeta {
  return (KIND_META as Record<string, KindMeta>)[kind] ?? KIND_META.unknown;
}

/** Narrow a server- or storage-supplied string to a Kind, checked rather than
 *  cast: discovery and localStorage are both outside the type system, and an
 *  unrecognised value must land on "unknown" (which is not connectable) instead
 *  of being smuggled through as if it were a supported kind. */
export function asKind(kind: string | undefined | null): Kind {
  return kind != null && kind in KIND_META ? (kind as Kind) : "unknown";
}
