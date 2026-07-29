import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "../ds/Button";
import { ConfirmDialog } from "../ds/ConfirmDialog";
import { DataTable } from "../ds/DataTable";
import { GroupBox } from "../ds/GroupBox";
import { adminApi, type Session } from "./api";

/** What identifies the instrument in a row: its address, or "Mock" when it isn't real hardware. */
function formatInstrument(session: Session): string {
  return session.mock ? `${session.label} (Mock)` : `${session.label} (${session.address})`;
}

function formatIdle(seconds: number): string {
  return `${seconds}s idle`;
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong.";
}

// Idle time is the one value whose entire purpose is freshness, so it is
// refetched rather than left at whatever it was when the page loaded.
const POLL_INTERVAL_MS = 10_000;

export function Sessions() {
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [error, setError] = useState("");

  const [closeTarget, setCloseTarget] = useState<Session | null>(null);
  const [closing, setClosing] = useState(false);
  const [releasingId, setReleasingId] = useState<string | null>(null);

  const requestId = useRef(0);

  const loadSessions = useCallback(async () => {
    const id = ++requestId.current;
    try {
      setError("");
      const rows = await adminApi.sessions();
      if (id === requestId.current) setSessions(rows);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  // Paused while a confirmation is open: re-sorting the list under someone who
  // is reading "Close bench-a?" is how the wrong session gets closed.
  useEffect(() => {
    if (closeTarget) return;
    const timer = setInterval(() => void loadSessions(), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [closeTarget, loadSessions]);

  const release = async (session: Session) => {
    setError("");
    setReleasingId(session.id);
    try {
      await adminApi.releaseSession(session.id);
      await loadSessions();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setReleasingId(null);
    }
  };

  const confirmClose = async () => {
    if (!closeTarget) return;
    setError("");
    setClosing(true);
    try {
      await adminApi.closeSession(closeTarget.id);
      setCloseTarget(null);
      await loadSessions();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setClosing(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      {error ? (
        <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {error}
        </p>
      ) : null}

      <GroupBox title="Live sessions">
        {sessions === null ? (
          <p style={{ color: "var(--text-muted)" }}>Loading…</p>
        ) : sessions.length === 0 ? (
          <p style={{ color: "var(--text-muted)" }}>
            No live sessions. Sessions appear here when someone opens an instrument.
          </p>
        ) : (
          <DataTable
            columns={["Instrument", "Owner", { label: "Viewers", width: "5.5rem", align: "right", mono: true }, { label: "Idle", width: "7rem", align: "right", mono: true }, ""]}
            rows={sessions.map((session) => [
              formatInstrument(session),
              session.owner || "—",
              session.viewers,
              formatIdle(session.idle_seconds),
              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                <Button size="sm" disabled={releasingId === session.id} onClick={() => void release(session)}>
                  Release
                </Button>
                <Button size="sm" variant="danger" disabled={releasingId === session.id} onClick={() => setCloseTarget(session)}>
                  Close
                </Button>
              </div>,
            ])}
          />
        )}
      </GroupBox>

      {closeTarget ? (
        <ConfirmDialog
          title={`Close ${closeTarget.label}?`}
          confirmLabel="Close"
          busy={closing}
          onCancel={() => setCloseTarget(null)}
          onConfirm={() => void confirmClose()}
          body={
            <>
              This ends the session immediately, and anyone viewing it loses their view right now.
              {closeTarget.recording ? " This session is recording — closing it stops that capture." : null}
            </>
          }
        />
      ) : null}
    </div>
  );
}
