import { ApiError, api } from "../../api/client";
import { Button } from "../../ds/Button";
import { StatusIndicator } from "../../ds/StatusIndicator";
import { useIdentity } from "../../store/identity";
import { useSession } from "../../store/session";
import { OwnerBadge } from "../sessions/OwnerBadge";
import { TERMINAL_DRAWER_ID } from "./TerminalDrawer";
import { useTerminalDrawer } from "./useTerminalDrawer";

/** The shell's chrome: what instrument this is, and the controls that belong to
 *  the session rather than to any one instrument kind. Everything here works
 *  the same for a scope, a power supply or a generator, which is why it lives
 *  in the shell and not in a kind's view. */
export function AppHeader() {
  const status = useSession((s) => s.status);
  const session = useSession((s) => s.session);
  const identity = useIdentity((s) => s.identity);
  const terminalOpen = useTerminalDrawer((s) => s.open);
  const toggleTerminal = useTerminalDrawer((s) => s.toggle);

  async function disconnect() {
    if (!session) return;
    try {
      await api.deleteSession(session.id);
    } catch {
      // already gone server-side (404) or unreachable — we disconnect locally regardless
    } finally {
      useSession.getState().clearSession();
    }
  }

  async function refreshSession() {
    if (!session) return;
    try {
      // Ownership changed; the readings did not. applySessionInfo replaces the
      // session record without clearing the instrument slices.
      useSession.getState().applySessionInfo(await api.getSession(session.id));
    } catch (caught) {
      // The claim itself already succeeded server-side -- OwnerBadge only
      // calls onClaimed after api.claimSession resolves. This refresh is only
      // what lets *this tab* stop showing read-only; if it fails, leaving the
      // badge up is the honest state, not a bug: ownership could not be
      // re-confirmed here, and the server enforces it regardless of what this
      // tab displays. The failure must still reach the user, through the same
      // banner every other session-level failure uses.
      useSession.getState().setError(caught instanceof ApiError ? caught.detail || caught.message : caught instanceof Error ? caught.message : "Could not refresh session after claim.");
    }
  }

  return (
    <header style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", padding: "10px 14px", background: "var(--lc-panel)", borderBottom: "1px solid var(--lc-border)" }}>
      <strong style={{ color: "var(--lc-text)" }}>SCPI Instrument Control</strong>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--lc-muted)" }}>{session ? `${session.model} · ${session.address ?? "mock"}` : "no instrument"}</span>
      {/* One right-hand group claims the auto margin, rather than passing it
          between whichever control happens to be rendered. */}
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
        {session !== null && identity != null && <OwnerBadge session={session} identity={identity} onClaimed={() => void refreshSession()} />}
        {session !== null && (
          <button
            type="button"
            id="terminal-toggle"
            onClick={toggleTerminal}
            aria-expanded={terminalOpen}
            aria-controls={TERMINAL_DRAWER_ID}
            style={{ fontSize: "var(--text-sm)", fontFamily: "var(--font-ui)", padding: "4px 10px", borderRadius: "var(--lc-radius-sm)", border: "1px solid var(--lc-border-strong)", color: "var(--lc-text)", background: terminalOpen ? "var(--lc-accent-soft)" : "transparent", cursor: "pointer" }}
          >
            Terminal
          </button>
        )}
        <StatusIndicator state={status} />
        {session !== null && (
          <Button variant="danger" onClick={() => void disconnect()}>
            Disconnect
          </Button>
        )}
      </div>
    </header>
  );
}
