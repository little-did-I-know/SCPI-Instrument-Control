import { ConnectDialog } from "./features/connect/ConnectDialog";
import { WaveformCanvas } from "./features/waveform/WaveformCanvas";
import { StatusIndicator } from "./ds/StatusIndicator";
import { useStream } from "./stream/useStream";
import { useSession } from "./store/session";

export default function App() {
  const status = useSession((s) => s.status);
  const session = useSession((s) => s.session);
  useStream(session?.id ?? null);
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--lc-bg)", fontFamily: "var(--font-ui)" }}>
      <header style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", padding: "10px 14px", background: "var(--lc-panel)", borderBottom: "1px solid var(--lc-border)" }}>
        <strong style={{ color: "var(--lc-text)" }}>SCPI Instrument Control</strong>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--lc-muted)" }}>{session ? `${session.model} · ${session.address ?? "mock"}` : "no instrument"}</span>
        <span style={{ marginLeft: "auto" }}>
          <StatusIndicator state={status} />
        </span>
      </header>
      <main style={{ flex: 1, padding: "var(--space-3)", color: "var(--lc-text)", display: "flex", flexDirection: "column" }}>
        {session === null && <ConnectDialog onConnected={(s) => useSession.getState().setSession(s)} />}
        {session !== null && <WaveformCanvas />}
      </main>
    </div>
  );
}
