import { TokenGate } from "./features/auth/TokenGate";
import { HomeScreen } from "./features/home/HomeScreen";
import { InstrumentShell } from "./features/shell/InstrumentShell";
import { TERMINAL_DRAWER_ID } from "./features/shell/TerminalDrawer";
import { useTerminalDrawer } from "./features/shell/useTerminalDrawer";
import { StatusIndicator } from "./ds/StatusIndicator";
import { useStream } from "./stream/useStream";
import { useSession } from "./store/session";

export default function App() {
  const status = useSession((s) => s.status);
  const session = useSession((s) => s.session);
  const terminalOpen = useTerminalDrawer((s) => s.open);
  const toggleTerminal = useTerminalDrawer((s) => s.toggle);
  useStream(session?.id ?? null);
  return (
    <TokenGate>
      <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--lc-bg)", fontFamily: "var(--font-ui)" }}>
        <header style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", padding: "10px 14px", background: "var(--lc-panel)", borderBottom: "1px solid var(--lc-border)" }}>
          <strong style={{ color: "var(--lc-text)" }}>SCPI Instrument Control</strong>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--lc-muted)" }}>{session ? `${session.model} · ${session.address ?? "mock"}` : "no instrument"}</span>
          {session !== null && (
            <button
              type="button"
              id="terminal-toggle"
              onClick={toggleTerminal}
              aria-expanded={terminalOpen}
              aria-controls={TERMINAL_DRAWER_ID}
              style={{ marginLeft: "auto", fontSize: "var(--text-sm)", fontFamily: "var(--font-ui)", padding: "4px 10px", borderRadius: "var(--lc-radius-sm)", border: "1px solid var(--lc-border-strong)", color: "var(--lc-text)", background: terminalOpen ? "var(--lc-accent-soft)" : "transparent", cursor: "pointer" }}
            >
              Terminal
            </button>
          )}
          <span style={{ marginLeft: session === null ? "auto" : undefined }}>
            <StatusIndicator state={status} />
          </span>
        </header>
        <main style={{ flex: 1, padding: "var(--space-3)", color: "var(--lc-text)", display: "flex", flexDirection: "column", gap: "var(--space-3)", minHeight: 0 }}>
          {session === null ? <HomeScreen onConnected={(s) => useSession.getState().setSession(s)} /> : <InstrumentShell />}
        </main>
      </div>
    </TokenGate>
  );
}
