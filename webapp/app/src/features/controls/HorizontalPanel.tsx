import { useState } from "react";
import { ApiError, api } from "../../api/client";
import { GroupBox } from "../../ds/GroupBox";
import { useSession } from "../../store/session";

// The 1-2-5 ladder, 1 ns/div to 10 s/div -- the SDS824X HD's supported
// horizontal range. No timebase-range query exists in scpi_commands.py to
// derive this at runtime, so the endpoints are a documented constant, same
// as scpi_control/gui/widgets/timebase_control.py's TIME_SCALES (the desktop
// GUI's equivalent control). Keep the two lists in sync if either changes.
//
// A click can only move to an adjacent rung, and the rungs themselves never
// go negative or fall below 1 ns/1 ns-equivalent resolution -- the ladder IS
// the bound, by construction, not a min/max layered on top of it.
const TIMEBASE_LADDER: ReadonlyArray<{ seconds: number; label: string }> = [
  { seconds: 1e-9, label: "1 ns" },
  { seconds: 2e-9, label: "2 ns" },
  { seconds: 5e-9, label: "5 ns" },
  { seconds: 10e-9, label: "10 ns" },
  { seconds: 20e-9, label: "20 ns" },
  { seconds: 50e-9, label: "50 ns" },
  { seconds: 100e-9, label: "100 ns" },
  { seconds: 200e-9, label: "200 ns" },
  { seconds: 500e-9, label: "500 ns" },
  { seconds: 1e-6, label: "1 µs" },
  { seconds: 2e-6, label: "2 µs" },
  { seconds: 5e-6, label: "5 µs" },
  { seconds: 10e-6, label: "10 µs" },
  { seconds: 20e-6, label: "20 µs" },
  { seconds: 50e-6, label: "50 µs" },
  { seconds: 100e-6, label: "100 µs" },
  { seconds: 200e-6, label: "200 µs" },
  { seconds: 500e-6, label: "500 µs" },
  { seconds: 1e-3, label: "1 ms" },
  { seconds: 2e-3, label: "2 ms" },
  { seconds: 5e-3, label: "5 ms" },
  { seconds: 10e-3, label: "10 ms" },
  { seconds: 20e-3, label: "20 ms" },
  { seconds: 50e-3, label: "50 ms" },
  { seconds: 100e-3, label: "100 ms" },
  { seconds: 200e-3, label: "200 ms" },
  { seconds: 500e-3, label: "500 ms" },
  { seconds: 1, label: "1 s" },
  { seconds: 2, label: "2 s" },
  { seconds: 5, label: "5 s" },
  { seconds: 10, label: "10 s" },
];

const DEFAULT_TIMEBASE = 1e-3; // 1 ms/div -- used only before any scope state has arrived.

/** Index of the ladder rung closest to `seconds`. Hardware echoes a value
 *  back through the same float wire format it was sent in, so this tolerates
 *  representational noise instead of requiring bit-exact equality. */
function nearestIndex(seconds: number): number {
  let best = 0;
  let bestDiff = Infinity;
  for (let i = 0; i < TIMEBASE_LADDER.length; i++) {
    const diff = Math.abs(TIMEBASE_LADDER[i].seconds - seconds);
    if (diff < bestDiff) {
      bestDiff = diff;
      best = i;
    }
  }
  return best;
}

/** HorizontalPanel -- owns the timebase (time/div). A horizontal control,
 *  not a trigger one: it used to live in TriggerPanel as a free-decimal
 *  SpinBox, which let a single stepper click send 101 ms/div from 1 ms/div
 *  and had no floor, so a negative sweep was one more click away. The ladder
 *  replaces both the step and the min/max: every reachable value is a
 *  documented 1-2-5 rung, so the instrument only ever sees a value it was
 *  designed to accept. */
export function HorizontalPanel() {
  const session = useSession((s) => s.session);
  const timebase = useSession((s) => s.scope?.timebase);
  const [error, setError] = useState<string | null>(null);

  const index = nearestIndex(timebase ?? DEFAULT_TIMEBASE);
  const current = TIMEBASE_LADDER[index];

  async function sendIndex(next: number) {
    if (!session) return;
    setError(null);
    try {
      await api.patchTimebase(session.id, TIMEBASE_LADDER[next].seconds);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  const stepperButtonStyle = (disabled: boolean) =>
    ({
      flex: 1,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      border: "none",
      borderLeft: "1px solid var(--lc-border)",
      background: "var(--lc-panel-2)",
      color: "var(--lc-text-2)",
      cursor: disabled ? "not-allowed" : "pointer",
      fontSize: "8px",
      lineHeight: 1,
      padding: 0,
    }) as const;

  return (
    <GroupBox title="Horizontal">
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-5)", fontSize: "var(--text-sm)" }}>
          Timebase
          <div
            style={{
              display: "inline-flex",
              alignItems: "stretch",
              height: "32px",
              width: "140px",
              background: "var(--lc-control)",
              border: "1px solid var(--lc-border-strong)",
              borderRadius: "var(--lc-radius-sm)",
              overflow: "hidden",
              fontFamily: "var(--font-ui)",
            }}
          >
            <span
              style={{
                flex: 1,
                minWidth: 0,
                display: "flex",
                alignItems: "center",
                padding: "0 8px",
                fontFamily: "var(--font-mono)",
                fontSize: "var(--text-sm)",
                color: "var(--lc-text)",
              }}
            >
              {current.label}
            </span>
            <div style={{ display: "flex", flexDirection: "column", width: "18px", borderTop: "none" }}>
              <button
                type="button"
                aria-label="Increase timebase"
                disabled={index >= TIMEBASE_LADDER.length - 1}
                onClick={() => sendIndex(index + 1)}
                style={{ ...stepperButtonStyle(index >= TIMEBASE_LADDER.length - 1), borderBottom: "1px solid var(--lc-border)" }}
              >
                ▲
              </button>
              <button
                type="button"
                aria-label="Decrease timebase"
                disabled={index <= 0}
                onClick={() => sendIndex(index - 1)}
                style={stepperButtonStyle(index <= 0)}
              >
                ▼
              </button>
            </div>
          </div>
          <span style={{ color: "var(--lc-text-2)" }}>/div</span>
        </div>
      </div>
      {error && (
        <div role="alert" style={{ padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {error}
        </div>
      )}
    </GroupBox>
  );
}
