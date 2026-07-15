import { useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import { getTrend, seedTrend, subscribeTrend } from "./trend";
import { Button } from "../../ds/Button";
import { GroupBox } from "../../ds/GroupBox";
import { useSession } from "../../store/session";

const linkStyle = { fontSize: "var(--text-sm)", fontFamily: "var(--font-ui)", padding: "6px 12px", borderRadius: "var(--lc-radius-sm)", border: "1px solid var(--lc-border-strong)", color: "var(--lc-text)", textDecoration: "none", alignSelf: "flex-start" } as const;
const mutedStyle = { color: "var(--lc-muted)", fontSize: "var(--text-sm)" } as const;

export function LogPanel() {
  const session = useSession((s) => s.session);
  const logStatus = useSession((s) => s.logStatus);
  const [rowCount, setRowCount] = useState(getTrend().rows.length);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => subscribeTrend(() => setRowCount(getTrend().rows.length)), []);

  // Seed status from the server on mount. Snapshot guard: a live log_status
  // broadcast that lands while this GET is in flight is fresher — never
  // clobber it with mount data (the useReferenceSeed pattern).
  useEffect(() => {
    if (!session) return;
    let stale = false;
    const before = useSession.getState().logStatus;
    api
      .getLog(session.id)
      .then((info) => {
        if (stale || useSession.getState().logStatus !== before) return;
        useSession.getState().applyLogStatus({ state: info.state, started_at: info.started_at, row_count: info.row_count, columns: info.columns });
      })
      .catch(() => {});
    // Backfill the shared trend buffer too: a tab that missed the start
    // broadcast (opened mid-recording, or refreshed) otherwise shows 0 rows
    // and skips live appends until the user enters Trend view.
    api
      .getLogData(session.id)
      .then((data) => {
        if (!stale) seedTrend(data);
      })
      .catch(() => {});
    return () => {
      stale = true;
    };
  }, [session?.id]);

  const recording = logStatus?.state === "recording";
  const hasLog = logStatus?.started_at != null;

  async function toggle() {
    if (!session) return;
    setError(null);
    try {
      // store update arrives via the log_status broadcast (this tab receives its own publish)
      if (recording) await api.logStop(session.id);
      else await api.logStart(session.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  const startedText = logStatus?.started_at != null ? new Date(logStatus.started_at * 1000).toLocaleTimeString() : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <GroupBox title="Recording">
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <Button onClick={toggle}>{recording ? "Stop recording" : "Start recording"}</Button>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", color: "var(--lc-text)" }}>
            {recording ? `recording · ${rowCount} rows${startedText ? ` · since ${startedText}` : ""}` : hasLog ? `stopped · ${rowCount} rows` : "idle"}
          </div>
          <span style={mutedStyle}>Records the selected measurements at ~1 Hz. The selection is locked while recording.</span>
        </div>
      </GroupBox>
      <GroupBox title="Export">
        {session && hasLog ? (
          <a href={api.logCsvUrl(session.id)} download style={linkStyle}>
            Download CSV
          </a>
        ) : (
          <span style={{ ...linkStyle, color: "var(--lc-muted)", opacity: 0.6 }}>Download CSV</span>
        )}
      </GroupBox>
      {error && <div role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)" }}>{error}</div>}
    </div>
  );
}
