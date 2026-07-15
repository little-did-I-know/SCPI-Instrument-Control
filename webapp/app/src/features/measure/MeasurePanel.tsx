import { useEffect, useRef, useState } from "react";
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
  // It now carries only VALUES for display; the SELECTION lives in s.measurementConfig
  // (seeded via GET on mount, kept current via the measurements_config broadcast).
  const measurements = useSession((s) => s.measurements);
  const measurementConfig = useSession((s) => s.measurementConfig);
  const [error, setError] = useState<string | null>(null);
  // No local mirror of the acknowledged selection — the STORE's measurementConfig is the single
  // acknowledged-truth source. The mount GET, each PUT response, and every measurements_config
  // broadcast all write it (via applyMeasurementConfig), so an already-mounted panel — this rail,
  // or another tab that receives the broadcast — always reflects the live selection, even in
  // steady state (no remount required).
  //
  // Precedence: in-flight optimistic (`pending`) > acknowledged truth (`measurementConfig`).
  const [pending, setPending] = useState<Selection[] | null>(null);
  // Monotonic request id: a slow PUT must never settle the selection after a newer toggle
  // superseded it, or both boxes flap to unchecked and the next click drops them server-side.
  const requestId = useRef(0);

  // Seed the selection from the server on mount — the store's measurementConfig may still be
  // stale/empty at first render (it only updates via broadcast), so we GET it directly once per
  // session. This GET is slow relative to everything else that can happen after mount (a user
  // toggle settling its own acknowledged truth, or a real measurements_config broadcast arriving)
  // — applying it unconditionally on resolve would let a stale response clobber fresher truth
  // that already landed in the store. So we snapshot "nothing has happened yet" at the moment the
  // request goes out and only apply the result if that's still true when it comes back;
  // otherwise the newer source (a toggle's PUT response, or a broadcast) already won.
  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    const requestIdAtStart = requestId.current;
    const configAtStart = useSession.getState().measurementConfig;
    api.getMeasurements(session.id).then((result) => {
      const noToggleSince = requestId.current === requestIdAtStart;
      const noBroadcastSince = useSession.getState().measurementConfig === configAtStart;
      if (!cancelled && noToggleSince && noBroadcastSince) {
        useSession.getState().applyMeasurementConfig(result.measurements);
      }
    }).catch(() => {
      // no server truth available yet (e.g. modern-dialect scope) — fall through to the
      // measurementConfig broadcast / default-empty precedence below.
    });
    return () => { cancelled = true; };
  }, [session?.id]);

  const selected: Selection[] = pending ?? measurementConfig;
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
    const id = ++requestId.current;
    setPending(next);
    setError(null);
    try {
      const result = await api.setMeasurements(session.id, next);
      if (id === requestId.current) {
        useSession.getState().applyMeasurementConfig(result.measurements); // durable across the empty-list broadcast gap
        setPending(null);
      }
      // else: stale response, a newer toggle is in flight — it will settle the selection
    } catch (err) {
      if (id === requestId.current) {
        setError(err instanceof ApiError ? err.detail : String(err));
        setPending(null); // failed: fall back to the last known truth
      }
    }
  }

  // Only render values for measurements that are actually selected — a deselected one lingers in
  // the store (no empty-list broadcast) and would otherwise keep showing a stale row.
  const rows = measurements
    .filter((m) => isChecked(m.channel, m.mtype))
    .map((m) => [`C${m.channel}`, m.mtype, m.value === null ? "--" : m.value.toFixed(3)]);

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
