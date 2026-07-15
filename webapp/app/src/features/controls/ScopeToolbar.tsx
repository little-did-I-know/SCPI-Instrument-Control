import { useState } from "react";
import { ApiError, api } from "../../api/client";
import type { ChannelState, RunOp } from "../../api/types";
import { Button } from "../../ds/Button";
import { Toolbar, ToolbarSeparator } from "../../ds/Toolbar";
import { useSession } from "../../store/session";
import { ExportButton } from "../export/ExportButton";
import { ScreenshotButton } from "../export/ScreenshotButton";

// Stable reference: zustand v5 hands the selector straight to useSyncExternalStore
// with no memoization, so a fresh `{}` per snapshot would loop forever while scope is null.
const NO_CHANNELS: Record<string, ChannelState> = {};

export function ScopeToolbar() {
  const session = useSession((s) => s.session);
  const runState = useSession((s) => s.scope?.run_state);
  const channels = useSession((s) => s.scope?.channels ?? NO_CHANNELS);
  const enabled = Object.entries(channels)
    .filter(([, channel]) => channel.enabled)
    .map(([key]) => Number(key))
    .sort((a, b) => a - b);
  const [error, setError] = useState<string | null>(null);

  const linkStyle = { fontSize: "var(--text-sm)", fontFamily: "var(--font-ui)", padding: "6px 12px", borderRadius: "var(--lc-radius-sm)", border: "1px solid var(--lc-border-strong)", color: "var(--lc-text)", textDecoration: "none" } as const;
  const disabledLinkStyle = { ...linkStyle, color: "var(--lc-muted)", opacity: 0.6 };

  async function op(next: RunOp) {
    if (!session) return;
    setError(null);
    try {
      await api.runOp(session.id, next);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  async function disconnect() {
    if (!session) return;
    setError(null);
    try {
      await api.deleteSession(session.id);
    } catch {
      // already gone server-side (404) or unreachable — we're disconnecting locally regardless
    } finally {
      useSession.getState().clearSession();
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <Toolbar
        right={
          <>
            <ExportButton />
            {!session || enabled.length === 0 ? (
              <span style={disabledLinkStyle}>JSON</span>
            ) : (
              <a href={api.waveformJsonUrl(session.id, enabled)} download style={linkStyle}>
                JSON
              </a>
            )}
            <ScreenshotButton />
            <Button variant="danger" onClick={disconnect}>Disconnect</Button>
          </>
        }
      >
        <Button variant="ghost" onClick={() => op("run")}>Run</Button>
        <Button variant="ghost" onClick={() => op("stop")}>Stop</Button>
        <Button variant="ghost" onClick={() => op("single")}>Single</Button>
        <Button variant="ghost" onClick={() => op("auto")}>Auto</Button>
        <ToolbarSeparator />
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", color: "var(--lc-text-2)" }}>{runState}</span>
      </Toolbar>
      {error && (
        <div role="alert" style={{ padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {error}
        </div>
      )}
    </div>
  );
}
