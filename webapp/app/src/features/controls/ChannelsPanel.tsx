import { useState } from "react";
import { ApiError, api } from "../../api/client";
import type { ChannelPatch, ChannelState } from "../../api/types";
import { Checkbox } from "../../ds/Checkbox";
import { ComboBox } from "../../ds/ComboBox";
import { GroupBox } from "../../ds/GroupBox";
import { SpinBox } from "../../ds/SpinBox";
import { useSession } from "../../store/session";

// Stable reference: zustand v5 hands the selector straight to useSyncExternalStore
// with no memoization, so a fresh `{}` per snapshot would loop forever while scope is null.
const NO_CHANNELS: Record<string, ChannelState> = {};

const COUPLINGS = ["DC", "AC", "GND"];
const PROBE_RATIOS = ["1", "10", "100"];

export function ChannelsPanel() {
  const session = useSession((s) => s.session);
  const channels = useSession((s) => s.scope?.channels ?? NO_CHANNELS);
  const [error, setError] = useState<string | null>(null);

  async function send(channel: number, patch: ChannelPatch) {
    if (!session) return;
    setError(null);
    try {
      await api.patchChannel(session.id, channel, patch);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  const numbers = Object.keys(channels)
    .map((key) => Number(key))
    .sort((a, b) => a - b);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      {numbers.map((n) => {
        const channel = channels[String(n)];
        return (
          <GroupBox key={n} title={`C${n}`} titleColor={`var(--ch${n})`}>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <Checkbox
                aria-label={`Enable C${n}`}
                checked={channel.enabled}
                onChange={(next) => send(n, { enabled: next })}
              />
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
                V/div
                <SpinBox
                  aria-label={`V/div C${n}`}
                  value={channel.voltage_scale}
                  step={0.1}
                  decimals={3}
                  suffix=" V"
                  onChange={(value) => send(n, { voltage_scale: value })}
                />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
                Offset
                <SpinBox
                  aria-label={`Offset C${n}`}
                  value={channel.voltage_offset}
                  step={0.1}
                  decimals={3}
                  suffix=" V"
                  onChange={(value) => send(n, { voltage_offset: value })}
                />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
                Coupling
                <ComboBox
                  aria-label={`Coupling C${n}`}
                  options={COUPLINGS}
                  value={channel.coupling}
                  onChange={(value) => send(n, { coupling: value })}
                />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
                Probe
                <ComboBox
                  aria-label={`Probe C${n}`}
                  options={channel.probe_ratio == null ? ["", ...PROBE_RATIOS] : PROBE_RATIOS}
                  value={channel.probe_ratio == null ? "" : String(channel.probe_ratio)}
                  onChange={(value) => send(n, { probe_ratio: Number(value) })}
                />
              </div>
            </div>
          </GroupBox>
        );
      })}
      {error && (
        <div role="alert" style={{ padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {error}
        </div>
      )}
    </div>
  );
}
