import { useState } from "react";
import { ApiError, api } from "../../api/client";
import type { ChannelState } from "../../api/types";
import { Checkbox } from "../../ds/Checkbox";
import { DataTable } from "../../ds/DataTable";
import { GroupBox } from "../../ds/GroupBox";
import { useSession } from "../../store/session";

// Stable reference: zustand v5 hands the selector straight to useSyncExternalStore
// with no memoization, so a fresh `{}` per snapshot would loop forever while scope is null.
const NO_CHANNELS: Record<string, ChannelState> = {};

const TYPES = ["PKPK", "AMPL", "MEAN", "RMS", "FREQ", "PER", "MAX", "MIN"];

type Selection = { channel: number; mtype: string };

export function MeasurePanel() {
  const session = useSession((s) => s.session);
  const channels = useSession((s) => s.scope?.channels ?? NO_CHANNELS);
  // s.measurements is already a stable array reference in the store — select it
  // directly (no `?? []` fallback, which would fabricate a new array every render).
  const measurements = useSession((s) => s.measurements);
  const [error, setError] = useState<string | null>(null);
  // No local mirror of the selection: the server is the source of truth. A local copy seeded
  // once at mount goes stale (the stream lags the PUT by up to a broadcast interval, and a rail
  // tab switch unmounts us), and since PUT /measurements is a FULL REPLACEMENT the next toggle
  // computed from a stale list would silently drop a measurement the server still has active.
  // `pending` is only an optimistic overlay for the in-flight toggle, so the checkbox responds
  // instantly; it clears when the PUT resolves and the streamed truth takes over again.
  const [pending, setPending] = useState<Selection[] | null>(null);

  const selected: Selection[] = pending ?? measurements.map((m) => ({ channel: m.channel, mtype: m.mtype }));
  const isChecked = (channel: number, mtype: string) =>
    selected.some((s) => s.channel === channel && s.mtype === mtype);

  const channelNumbers = Object.keys(channels)
    .map(Number)
    .filter((n) => channels[String(n)]?.enabled)
    .sort((a, b) => a - b);

  async function toggle(channel: number, mtype: string) {
    if (!session) return;
    const next = isChecked(channel, mtype)
      ? selected.filter((s) => !(s.channel === channel && s.mtype === mtype))
      : [...selected, { channel, mtype }];
    setPending(next);
    setError(null);
    try {
      await api.setMeasurements(session.id, next);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setPending(null); // fall back to the server's truth
    }
  }

  const rows = measurements.map((m) => [
    `C${m.channel}`,
    m.mtype,
    m.value === null ? "--" : m.value.toFixed(3),
  ]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <GroupBox title="Measurements">
        {channelNumbers.length === 0 && (
          <div style={{ color: "var(--lc-muted)", fontSize: "var(--text-sm)" }}>No channels enabled.</div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {channelNumbers.map((n) => (
            <div key={n}>
              <div style={{ fontWeight: "var(--weight-bold)", color: `var(--ch${n})`, marginBottom: "4px" }}>{`C${n}`}</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 14px" }}>
                {TYPES.map((mtype) => (
                  <Checkbox
                    key={mtype}
                    aria-label={`${mtype} C${n}`}
                    label={mtype}
                    checked={isChecked(n, mtype)}
                    onChange={() => toggle(n, mtype)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </GroupBox>

      {selected.length === 0 && (
        <div style={{ color: "var(--lc-muted)", fontSize: "var(--text-sm)" }}>
          Select a measurement above to see live values.
        </div>
      )}

      {session?.dialect === "modern" && (
        <div style={{ color: "var(--lc-muted)", fontSize: "var(--text-sm)" }}>
          Measurements are unavailable on modern-dialect scopes.
        </div>
      )}

      <DataTable
        columns={["Ch", "Measurement", { label: "Value", align: "right", mono: true }]}
        rows={rows}
      />

      {error && (
        <div role="alert" style={{ padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {error}
        </div>
      )}
    </div>
  );
}
