import { useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import type { PsuOutputState } from "../../api/types";
import { GroupBox } from "../../ds/GroupBox";
import { Reading } from "../../ds/Reading";
import { SpinBox } from "../../ds/SpinBox";
import { StatusIndicator } from "../../ds/StatusIndicator";
import { useSession } from "../../store/session";

// Stable reference: an inline `[]` fallback would be a fresh array every
// render, which would loop the zustand selector forever (same issue as
// ChannelsPanel's NO_CHANNELS).
const NO_OUTPUTS: PsuOutputState[] = [];

function fmt(value: number): string {
  return (typeof value === "number" && !Number.isNaN(value) ? value : 0).toFixed(3);
}

export function PsuPanel() {
  const session = useSession((s) => s.session);
  const sessionId = session?.id ?? null;
  const psu = useSession((s) => s.psu);
  const outputs = psu?.outputs ?? NO_OUTPUTS;
  const [error, setError] = useState<string | null>(null);
  // Output numbers with a PATCH in flight: guards against a double-click
  // sending two conflicting requests, and disables the setpoint fields
  // while their value is unconfirmed.
  const [pending, setPending] = useState<ReadonlySet<number>>(new Set());

  // Initial load: App.tsx already runs useStream(), which subscribes to this
  // session's WebSocket and writes any psu frame into the shared store (see
  // useStream.ts / store/session.ts). But PsuPanel's own mount effect fires
  // before that subscription's effect does (child effects commit before the
  // parent's), so without this fetch the panel would sit empty until the
  // stream happens to deliver its first frame. This fetch is what actually
  // populates the store on a cold mount; the stream then keeps it live.
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    api
      .psuState(sessionId)
      .then((state) => {
        if (!cancelled && Array.isArray(state?.outputs)) useSession.getState().applyPsuState(state);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  function withPending(n: number, fn: () => Promise<void>): Promise<void> {
    setPending((prev) => new Set(prev).add(n));
    return fn().finally(() => {
      setPending((prev) => {
        const next = new Set(prev);
        next.delete(n);
        return next;
      });
    });
  }

  async function sendOutput(n: number, patch: { voltage?: number; current?: number }) {
    if (!sessionId) return;
    setError(null);
    await withPending(n, async () => {
      try {
        const state = await api.setPsuOutput(sessionId, n, patch);
        useSession.getState().applyPsuState(state);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
        // Same reasoning as sendEnable below: a partially-applied PATCH
        // (e.g. voltage landed, current rejected) must not leave stale
        // fields on screen, so reconcile with the instrument's own state.
        await reconcile(sessionId);
      }
    });
  }

  async function sendEnable(n: number, enabled: boolean) {
    if (!sessionId) return;
    setError(null);
    await withPending(n, async () => {
      try {
        const state = await api.setPsuOutputEnable(sessionId, n, enabled);
        useSession.getState().applyPsuState(state);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
        // The toggle must never lie about instrument state: a failed enable
        // request could have partially landed on the hardware, so reconcile
        // with the server's own view rather than leaving stale local state.
        await reconcile(sessionId);
      }
    });
  }

  async function reconcile(id: string) {
    try {
      const fresh = await api.psuState(id);
      useSession.getState().applyPsuState(fresh);
    } catch {
      // best effort: keep whatever we last knew to be true
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      {psu === null && !error && <p style={{ margin: 0, color: "var(--lc-muted)" }}>Loading power supply state…</p>}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
        {outputs.map((o) => {
          const busy = pending.has(o.output);
          return (
            <GroupBox key={o.output} title={`Output ${o.output}`}>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", minWidth: "220px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
                  Voltage
                  <SpinBox
                    aria-label={`Output ${o.output} voltage`}
                    value={o.voltage}
                    step={0.1}
                    min={0}
                    decimals={3}
                    suffix=" V"
                    disabled={busy}
                    onChange={(value) => sendOutput(o.output, { voltage: value })}
                  />
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
                  Current limit
                  <SpinBox
                    aria-label={`Output ${o.output} current`}
                    value={o.current}
                    step={0.1}
                    min={0}
                    decimals={3}
                    suffix=" A"
                    disabled={busy}
                    onChange={(value) => sendOutput(o.output, { current: value })}
                  />
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={o.enabled}
                  aria-label={`Output ${o.output} enable`}
                  disabled={busy}
                  onClick={() => sendEnable(o.output, !o.enabled)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    alignSelf: "flex-start",
                    gap: "8px",
                    padding: "4px 10px",
                    border: "1px solid var(--lc-border-strong)",
                    borderRadius: "var(--lc-radius-sm)",
                    background: "var(--lc-control)",
                    cursor: busy ? "not-allowed" : "pointer",
                    opacity: busy ? 0.6 : 1,
                  }}
                >
                  <StatusIndicator state={o.enabled ? "connected" : "disconnected"} label={o.enabled ? "Output on" : "Output off"} />
                </button>
                <div style={{ display: "flex", gap: "var(--space-3)", paddingTop: "4px", borderTop: "1px solid var(--lc-border)" }}>
                  <Reading label="V" value={fmt(o.measured_voltage)} unit="V" />
                  <Reading label="I" value={fmt(o.measured_current)} unit="A" />
                  <Reading label="P" value={fmt(o.measured_power)} unit="W" />
                </div>
              </div>
            </GroupBox>
          );
        })}
      </div>
      {error && (
        <div role="alert" style={{ padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {error}
        </div>
      )}
    </div>
  );
}
