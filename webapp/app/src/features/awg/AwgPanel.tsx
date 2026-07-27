import { useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import type { AwgChannelPatch, AwgChannelState } from "../../api/types";
import { Button } from "../../ds/Button";
import { ComboBox } from "../../ds/ComboBox";
import { GroupBox } from "../../ds/GroupBox";
import { SpinBox } from "../../ds/SpinBox";
import { StatusIndicator } from "../../ds/StatusIndicator";
import { useSession } from "../../store/session";

// Stable reference: zustand v5 hands the selector straight to
// useSyncExternalStore with no memoization, so a fresh `[]` per snapshot would
// loop forever while awg is null (same as PsuPanel's NO_OUTPUTS).
const NO_CHANNELS: AwgChannelState[] = [];

// Exactly the server's ALLOWED_FUNCTIONS, which is exactly the driver's
// WaveformType. ARB is offered but carries no waveform-upload UI yet: selecting
// it switches the instrument to whatever arbitrary waveform it already holds.
const FUNCTIONS = ["SINE", "SQUARE", "RAMP", "PULSE", "NOISE", "ARB", "DC"];

/** A setpoint the instrument would not report. An editable field pre-filled
 *  with 0 would invite the user to "confirm" a value that was never read back,
 *  so show the unreadable marker instead of a spin box. */
function Unreadable({ what, unit }: { what: string; unit: string }) {
  return (
    <span aria-label={what} title="This value could not be read from the instrument" style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", color: "var(--lc-muted)" }}>
      --.-- {unit}
    </span>
  );
}

export function AwgPanel() {
  const sessionId = useSession((s) => s.session?.id ?? null);
  const channels = useSession((s) => s.awg?.channels ?? NO_CHANNELS);
  const loaded = useSession((s) => s.awg !== null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<ReadonlySet<number>>(new Set());

  // Cold mount: App's useStream subscribes in a parent effect, which commits
  // AFTER this child's, so without this fetch the panel sits empty until the
  // stream happens to deliver its first frame. This fetch populates the store;
  // the stream then keeps it live. Task 5's readout reads the same slice.
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    api
      .awgState(sessionId)
      .then((state) => {
        if (!cancelled && Array.isArray(state?.channels)) useSession.getState().applyAwgState(state);
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

  async function reconcile(id: string) {
    try {
      useSession.getState().applyAwgState(await api.awgState(id));
    } catch {
      // best effort: keep whatever we last knew to be true
    }
  }

  async function sendChannel(n: number, patch: AwgChannelPatch) {
    if (!sessionId) return;
    setError(null);
    await withPending(n, async () => {
      try {
        useSession.getState().applyAwgState(await api.setAwgChannel(sessionId, n, patch));
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
        // A partially-applied PATCH (frequency landed, amplitude rejected) must
        // not leave stale fields on screen: ask the instrument what is true.
        await reconcile(sessionId);
      }
    });
  }

  async function sendEnable(n: number, enabled: boolean) {
    if (!sessionId) return;
    setError(null);
    await withPending(n, async () => {
      try {
        useSession.getState().applyAwgState(await api.setAwgChannelEnable(sessionId, n, enabled));
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
        await reconcile(sessionId);
      }
    });
  }

  async function killOutputs() {
    if (!sessionId) return;
    setError(null);
    try {
      useSession.getState().applyAwgState(await api.allAwgOutputsOff(sessionId));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
      await reconcile(sessionId);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      {!loaded && !error && <p style={{ margin: 0, color: "var(--lc-muted)" }}>Loading generator state…</p>}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
        {channels.map((c) => {
          const busy = pending.has(c.channel);
          const enableUnknown = c.enabled === null;
          return (
            <GroupBox key={c.channel} title={`Channel ${c.channel}`}>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", minWidth: "240px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
                  Function
                  {c.function === null ? (
                    <Unreadable what={`Channel ${c.channel} function`} unit="" />
                  ) : (
                    <ComboBox
                      aria-label={`Channel ${c.channel} function`}
                      options={FUNCTIONS}
                      value={c.function}
                      disabled={busy}
                      onChange={(value) => sendChannel(c.channel, { function: value })}
                    />
                  )}
                </div>
                <Field label="Frequency" what={`Channel ${c.channel} frequency`} value={c.frequency} unit=" Hz" step={100} min={0} busy={busy} onChange={(v) => sendChannel(c.channel, { frequency: v })} />
                <Field label="Amplitude" what={`Channel ${c.channel} amplitude`} value={c.amplitude} unit=" Vpp" step={0.1} min={0} busy={busy} onChange={(v) => sendChannel(c.channel, { amplitude: v })} />
                {/* Offset deliberately has NO min: a DC offset is signed, and a
                    floor of 0 would silently forbid every negative offset. */}
                <Field label="Offset" what={`Channel ${c.channel} offset`} value={c.offset} unit=" V" step={0.1} busy={busy} onChange={(v) => sendChannel(c.channel, { offset: v })} />
                <Field label="Phase" what={`Channel ${c.channel} phase`} value={c.phase} unit="°" step={1} min={0} busy={busy} onChange={(v) => sendChannel(c.channel, { phase: v })} />
                {c.function === "PULSE" && (
                  <Field label="Duty cycle" what={`Channel ${c.channel} duty cycle`} value={c.duty_cycle} unit=" %" step={1} min={0} busy={busy} onChange={(v) => sendChannel(c.channel, { duty_cycle: v })} />
                )}
                {c.function === "RAMP" && (
                  <Field label="Symmetry" what={`Channel ${c.channel} symmetry`} value={c.symmetry} unit=" %" step={1} min={0} busy={busy} onChange={(v) => sendChannel(c.channel, { symmetry: v })} />
                )}
                <button
                  type="button"
                  role="switch"
                  aria-checked={enableUnknown ? "mixed" : c.enabled === true}
                  aria-label={`Channel ${c.channel} enable`}
                  disabled={busy || enableUnknown}
                  title={enableUnknown ? "This model does not report the output state; read it off the instrument's own display." : undefined}
                  onClick={() => sendEnable(c.channel, !c.enabled)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    alignSelf: "flex-start",
                    gap: "8px",
                    padding: "4px 10px",
                    border: "1px solid var(--lc-border-strong)",
                    borderRadius: "var(--lc-radius-sm)",
                    background: "var(--lc-control)",
                    cursor: busy || enableUnknown ? "not-allowed" : "pointer",
                    opacity: busy || enableUnknown ? 0.6 : 1,
                  }}
                >
                  <StatusIndicator state={enableUnknown ? "error" : c.enabled ? "connected" : "disconnected"} label={enableUnknown ? "Output state unknown" : c.enabled ? "Output on" : "Output off"} />
                </button>
              </div>
            </GroupBox>
          );
        })}
      </div>
      {channels.length > 0 && (
        <div>
          <Button variant="danger" onClick={killOutputs}>
            All outputs off
          </Button>
        </div>
      )}
      {error && (
        <div role="alert" style={{ padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {error}
        </div>
      )}
    </div>
  );
}

/** One labelled numeric setpoint, or the unreadable marker when the instrument
 *  would not report it. Extracted because an AWG channel has six of them and
 *  the null-vs-zero rule must read identically for every one. */
function Field({ label, what, value, unit, step, min, busy, onChange }: { label: string; what: string; value: number | null; unit: string; step: number; min?: number; busy: boolean; onChange: (value: number) => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
      {label}
      {value === null ? <Unreadable what={what} unit={unit.trim()} /> : <SpinBox aria-label={what} value={value} step={step} min={min} decimals={3} suffix={unit} disabled={busy} onChange={onChange} />}
    </div>
  );
}
