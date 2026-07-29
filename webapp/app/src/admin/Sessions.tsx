import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "../ds/Button";
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

export function Sessions() {
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [error, setError] = useState("");

  const [closeTarget, setCloseTarget] = useState<Session | null>(null);
  const [closing, setClosing] = useState(false);
  const [releasingId, setReleasingId] = useState<string | null>(null);

  const dialogRef = useRef<HTMLDivElement>(null);

  const loadSessions = useCallback(async () => {
    try {
      setError("");
      setSessions(await adminApi.sessions());
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  // Move focus into the confirmation so keyboard and screen-reader users land
  // on it rather than having to hunt for a dialog that appeared elsewhere.
  useEffect(() => {
    if (closeTarget) dialogRef.current?.focus();
  }, [closeTarget]);

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
          <p>Loading…</p>
        ) : sessions.length === 0 ? (
          <p>No live sessions.</p>
        ) : (
          <DataTable
            columns={["Instrument", "Owner", "Viewers", "Idle", ""]}
            rows={sessions.map((session) => [
              formatInstrument(session),
              session.owner || "—",
              session.viewers,
              formatIdle(session.idle_seconds),
              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                <Button
                  size="sm"
                  disabled={closeTarget !== null || releasingId !== null}
                  onClick={() => void release(session)}
                >
                  Release
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  disabled={closeTarget !== null || releasingId !== null}
                  onClick={() => setCloseTarget(session)}
                >
                  Close
                </Button>
              </div>,
            ])}
          />
        )}
      </GroupBox>

      {closeTarget ? (
        <div
          role="alertdialog"
          aria-label={`Close ${closeTarget.label}?`}
          aria-modal="true"
          tabIndex={-1}
          ref={dialogRef}
          style={{
            border: "1px solid var(--lc-border-strong)",
            borderRadius: "var(--lc-radius)",
            background: "var(--lc-panel)",
            boxShadow: "var(--lc-elev-1)",
            padding: "var(--space-3)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-2)",
            maxWidth: "360px",
          }}
        >
          <p>
            Close {closeTarget.label}? This ends the session immediately, and anyone viewing it
            loses their view right now.
            {closeTarget.recording ? " This session is recording -- closing it stops that capture." : null}
          </p>
          <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
            <Button disabled={closing} onClick={() => setCloseTarget(null)}>
              Cancel
            </Button>
            <Button variant="danger" disabled={closing} onClick={() => void confirmClose()}>
              Close
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
