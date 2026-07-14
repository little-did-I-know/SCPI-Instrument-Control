import { useState } from "react";
import { ApiError, api } from "../../api/client";
import type { RunOp } from "../../api/types";
import { Button } from "../../ds/Button";
import { Toolbar, ToolbarSeparator } from "../../ds/Toolbar";
import { useSession } from "../../store/session";

export function ScopeToolbar() {
  const session = useSession((s) => s.session);
  const runState = useSession((s) => s.scope?.run_state);
  const [error, setError] = useState<string | null>(null);

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
      useSession.getState().clearSession();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <Toolbar right={<Button variant="danger" onClick={disconnect}>Disconnect</Button>}>
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
