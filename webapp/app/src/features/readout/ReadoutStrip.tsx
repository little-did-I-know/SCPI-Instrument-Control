import type { ChannelState, MeasurementValue } from "../../api/types";
import { Reading } from "../../ds/Reading";
import { useSession } from "../../store/session";

// Stable reference: zustand v5 hands the selector straight to useSyncExternalStore
// with no memoization, so a fresh `{}` per snapshot would loop forever while scope is null.
const NO_CHANNELS: Record<string, ChannelState> = {};

function formatValue(measurement: MeasurementValue | undefined): string {
  if (measurement === undefined || measurement.value === null || measurement.value === undefined) {
    return "--.--";
  }
  return measurement.value.toFixed(3);
}

export function ReadoutStrip() {
  const channels = useSession((s) => s.scope?.channels ?? NO_CHANNELS);
  // s.measurements is already a stable array reference in the store — select it
  // directly (no `?? []` fallback, which would fabricate a new array every render).
  const measurements = useSession((s) => s.measurements);

  const numbers = Object.keys(channels)
    .map((key) => Number(key))
    .filter((n) => channels[String(n)]?.enabled)
    .sort((a, b) => a - b);

  if (numbers.length === 0) return null;

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
      {numbers.map((n) => {
        const channel = channels[String(n)];
        const pkpk = measurements.find((m) => m.channel === n && m.mtype === "PKPK");
        const freq = measurements.find((m) => m.channel === n && m.mtype === "FREQ");
        return (
          <div
            key={n}
            style={{
              position: "relative",
              display: "flex",
              paddingLeft: "13px",
              paddingTop: "6px",
              paddingBottom: "6px",
              paddingRight: "14px",
              background: "var(--lc-panel)",
              border: "1px solid var(--lc-border)",
              borderRadius: "var(--lc-radius-sm)",
            }}
          >
            <span
              aria-hidden
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                bottom: 0,
                width: "5px",
                background: `var(--ch${n})`,
                borderTopLeftRadius: "var(--lc-radius-sm)",
                borderBottomLeftRadius: "var(--lc-radius-sm)",
              }}
            />
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span style={{ fontWeight: "var(--weight-bold)", color: `var(--ch${n})` }}>{`C${n}`}</span>
              <span style={{ fontSize: "var(--text-sm)", color: "var(--lc-muted)" }}>
                {`${channel.coupling} · ${channel.voltage_scale} V/div`}
              </span>
              <Reading value={formatValue(pkpk)} unit="V" size="lg" />
              {freq && <Reading label="FREQ" value={formatValue(freq)} unit="Hz" size="sm" />}
            </div>
          </div>
        );
      })}
    </div>
  );
}
