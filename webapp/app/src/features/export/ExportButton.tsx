import { api } from "../../api/client";
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

  const style = { fontSize: "var(--text-sm)", fontFamily: "var(--font-ui)", padding: "6px 12px", borderRadius: "var(--lc-radius-sm)", border: "1px solid var(--lc-border-strong)", color: "var(--lc-text)", textDecoration: "none" } as const;

  if (!session || enabled.length === 0) {
    return <span style={{ ...style, color: "var(--lc-muted)", opacity: 0.6 }}>Export CSV</span>;
  }
  return (
    <a href={api.captureUrl(session.id, enabled)} download style={style}>
      Export CSV
    </a>
  );
}
