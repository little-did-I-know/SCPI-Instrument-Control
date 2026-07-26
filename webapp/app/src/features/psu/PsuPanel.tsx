import { useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import { getToken } from "../../api/token";
import type { PsuOutputState } from "../../api/types";
import { GroupBox } from "../../ds/GroupBox";
import { Reading } from "../../ds/Reading";
import { SpinBox } from "../../ds/SpinBox";
import { StatusIndicator } from "../../ds/StatusIndicator";
import { useSession } from "../../store/session";

function fmt(value: number): string {
  return (typeof value === "number" && !Number.isNaN(value) ? value : 0).toFixed(3);
}

export function PsuPanel() {
  const session = useSession((s) => s.session);
  const sessionId = session?.id ?? null;
  const [outputs, setOutputs] = useState<PsuOutputState[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Initial load: the stream's first frame carries scope-shaped state, not psu
  // outputs, so the panel always needs its own fetch on mount.
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    api
      .psuState(sessionId)
      .then((state) => {
        if (!cancelled && Array.isArray(state?.outputs)) setOutputs(state.outputs);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // Live measured values: the gateway polls the instrument and republishes a
  // {type:"state", kind:"psu", outputs:[...]} frame on the same session stream
  // used by the scope view. Subscribe directly rather than through the scope
  // store, since that store has no concept of psu state.
  useEffect(() => {
    if (!sessionId) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const token = getToken();
    const subprotocols = token ? [`scpi-token.${token}`, "scpi"] : ["scpi"];
    const socket = new WebSocket(`${protocol}//${window.location.host}/api/sessions/${sessionId}/stream`, subprotocols);
    socket.onmessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data as string);
        if (message && message.type === "state" && message.kind === "psu" && Array.isArray(message.outputs)) {
          setOutputs(message.outputs);
        }
      } catch {
        // malformed frame: ignore, keep the last known-good outputs
      }
    };
    return () => {
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = null;
      socket.close();
    };
  }, [sessionId]);

  async function sendOutput(n: number, patch: { voltage?: number; current?: number }) {
    if (!sessionId) return;
    setError(null);
    try {
      const state = await api.setPsuOutput(sessionId, n, patch);
      setOutputs(state.outputs);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  async function sendEnable(n: number, enabled: boolean) {
    if (!sessionId) return;
    setError(null);
    try {
      const state = await api.setPsuOutputEnable(sessionId, n, enabled);
      setOutputs(state.outputs);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
      // The toggle must never lie about instrument state: a failed enable
      // request could have partially landed on the hardware, so reconcile
      // with the server's own view rather than leaving stale local state.
      try {
        const fresh = await api.psuState(sessionId);
        setOutputs(fresh.outputs);
      } catch {
        // best effort: keep whatever we last knew to be true
      }
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
        {outputs.map((o) => (
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
                  onChange={(value) => sendOutput(o.output, { current: value })}
                />
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={o.enabled}
                aria-label={`Output ${o.output} enable`}
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
                  cursor: "pointer",
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
        ))}
      </div>
      {error && (
        <div role="alert" style={{ padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {error}
        </div>
      )}
    </div>
  );
}
