import { useState } from "react";
import { ApiError, api } from "../../api/client";
import { downloadAuthenticated } from "../../api/download";
import type { ChannelState } from "../../api/types";
import { useSession } from "../../store/session";

// Stable reference: zustand v5 hands the selector straight to useSyncExternalStore
// with no memoization, so a fresh `{}` per snapshot would loop forever while scope is null.
const NO_CHANNELS: Record<string, ChannelState> = {};

export function ExportButton() {
  const session = useSession((s) => s.session);
  const channels = useSession((s) => s.scope?.channels ?? NO_CHANNELS);
  const enabled = Object.entries(channels)
    .filter(([, channel]) => channel.enabled)
    .map(([key]) => Number(key))
    .sort((a, b) => a - b);
  const [error, setError] = useState<string | null>(null);

  const style = { fontSize: "var(--text-sm)", fontFamily: "var(--font-ui)", padding: "6px 12px", borderRadius: "var(--lc-radius-sm)", border: "1px solid var(--lc-border-strong)", color: "var(--lc-text)", background: "transparent", cursor: "pointer" } as const;

  if (!session || enabled.length === 0) {
    return <span style={{ ...style, color: "var(--lc-muted)", opacity: 0.6 }}>Export CSV</span>;
  }

  async function handleClick() {
    if (!session) return;
    setError(null);
    try {
      await downloadAuthenticated(api.captureUrl(session.id, enabled), `capture_${session.id}_C${enabled.join("-")}.csv`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  return (
    <>
      <button type="button" onClick={handleClick} style={style}>
        Export CSV
      </button>
      {error && <div role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)" }}>{error}</div>}
    </>
  );
}
