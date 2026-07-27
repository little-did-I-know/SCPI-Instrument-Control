import type { AwgChannelState } from "../../api/types";
import { Reading } from "../../ds/Reading";
import { StatusIndicator } from "../../ds/StatusIndicator";
import { useSession } from "../../store/session";
import { fmt } from "../psu/format";

// Stable reference: a fresh `[]` per snapshot would loop the zustand selector
// forever while awg is null (same as PsuReadout's NO_OUTPUTS).
const NO_CHANNELS: AwgChannelState[] = [];

/** What the generator reports, in the shell's readout slot.
 *
 *  These are read-back values, not echoes of what was sent: an AWG clamps
 *  amplitude against its load setting and snaps frequency to its resolution, so
 *  what it reports can differ from what was asked for. Every channel appears,
 *  including disabled ones -- for a source, "is this output driving my circuit?"
 *  is exactly the question the strip exists to answer.
 */
export function AwgReadout() {
  const channels = useSession((s) => s.awg?.channels ?? NO_CHANNELS);
  if (channels.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
      {channels.map((c) => {
        // The switch in AwgPanel owns the aria-label "Channel N enable". This is
        // a read-only indicator with its own distinct accessible name, so a
        // full-app render has no duplicate names.
        const label = c.enabled === null ? `Channel ${c.channel} state unknown` : c.enabled ? `Channel ${c.channel} on` : `Channel ${c.channel} off`;
        return (
          <div
            key={c.channel}
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
                background: `var(--ch${c.channel})`,
                borderTopLeftRadius: "var(--lc-radius-sm)",
                borderBottomLeftRadius: "var(--lc-radius-sm)",
              }}
            />
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span style={{ fontWeight: "var(--weight-bold)", color: `var(--ch${c.channel})` }}>{`CH${c.channel}`}</span>
              <span style={{ fontSize: "var(--text-sm)", color: "var(--lc-muted)" }}>{c.function ?? "--"}</span>
              <StatusIndicator state={c.enabled === null ? "error" : c.enabled ? "connected" : "disconnected"} label={label} />
              <div style={{ display: "flex", gap: "var(--space-3)" }}>
                <Reading label="F" value={fmt(c.frequency)} unit="Hz" />
                <Reading label="A" value={fmt(c.amplitude)} unit="Vpp" />
                <Reading label="O" value={fmt(c.offset)} unit="V" />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
