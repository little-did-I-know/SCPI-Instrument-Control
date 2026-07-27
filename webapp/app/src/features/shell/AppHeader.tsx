import { StatusIndicator } from "../../ds/StatusIndicator";
import { useSession } from "../../store/session";
import { TERMINAL_DRAWER_ID } from "./TerminalDrawer";
import { useTerminalDrawer } from "./useTerminalDrawer";

/** The shell's chrome: what instrument this is, and the controls that belong to
 *  the session rather than to any one instrument kind. Everything here works
 *  the same for a scope, a power supply or a generator, which is why it lives
 *  in the shell and not in a kind's view. */
export function AppHeader() {
  const status = useSession((s) => s.status);
  const session = useSession((s) => s.session);
  const terminalOpen = useTerminalDrawer((s) => s.open);
  const toggleTerminal = useTerminalDrawer((s) => s.toggle);

  return (
    <header style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", padding: "10px 14px", background: "var(--lc-panel)", borderBottom: "1px solid var(--lc-border)" }}>
      <strong style={{ color: "var(--lc-text)" }}>SCPI Instrument Control</strong>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--lc-muted)" }}>{session ? `${session.model} · ${session.address ?? "mock"}` : "no instrument"}</span>
      {/* One right-hand group claims the auto margin, rather than passing it
          between whichever control happens to be rendered. */}
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
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
      </div>
    </header>
  );
}
