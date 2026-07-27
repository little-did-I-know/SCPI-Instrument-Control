import type { PsuOutputState } from "../../api/types";
import { Reading } from "../../ds/Reading";
import { StatusIndicator } from "../../ds/StatusIndicator";
import { useSession } from "../../store/session";
import { fmt } from "./format";

// Stable reference: zustand v5 hands the selector straight to
// useSyncExternalStore with no memoization, so a fresh `[]` per snapshot would
// loop forever while psu is null (same issue as PsuPanel's NO_OUTPUTS).
const NO_OUTPUTS: PsuOutputState[] = [];

/** What the supply reports, in the shell's readout slot: one card per output,
 *  measured V/I/P and whether the rail is live. The setpoints that command
 *  those values live in PsuPanel -- the strip is instrument truth, the body is
 *  intent. Mirrors ReadoutStrip, which does the same for a scope. */
export function PsuReadout() {
  const outputs = useSession((s) => s.psu?.outputs ?? NO_OUTPUTS);
  if (outputs.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
      {outputs.map((o) => {
        // The switch in PsuPanel owns the aria-label "Output N enable". This is
        // a read-only indicator with its own distinct accessible name, so a
        // full-app render has no duplicate names.
        const label = o.enabled === null ? `Output ${o.output} state unknown` : o.enabled ? `Output ${o.output} on` : `Output ${o.output} off`;
        return (
          <div
            key={o.output}
            style={{
              position: "relative",
              display: "flex",
              padding: "6px 14px 6px 13px",
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
                background: `var(--ch${o.output})`,
                borderTopLeftRadius: "var(--lc-radius-sm)",
                borderBottomLeftRadius: "var(--lc-radius-sm)",
              }}
            />
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span style={{ fontWeight: "var(--weight-bold)", color: `var(--ch${o.output})` }}>{`OUT${o.output}`}</span>
              <StatusIndicator state={o.enabled === null ? "error" : o.enabled ? "connected" : "disconnected"} label={label} />
              <div style={{ display: "flex", gap: "var(--space-3)" }}>
                <Reading label="V" value={fmt(o.measured_voltage)} unit="V" />
                <Reading label="I" value={fmt(o.measured_current)} unit="A" />
                <Reading label="P" value={fmt(o.measured_power)} unit="W" />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
