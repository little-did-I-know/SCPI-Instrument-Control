import { TokenGate } from "./features/auth/TokenGate";
import { HomeScreen } from "./features/home/HomeScreen";
import { AppHeader } from "./features/shell/AppHeader";
import { ErrorBanner } from "./features/shell/ErrorBanner";
import { InstrumentShell } from "./features/shell/InstrumentShell";
import { useStream } from "./stream/useStream";
import { useSession } from "./store/session";

export default function App() {
  const session = useSession((s) => s.session);
  useStream(session?.id ?? null);
  return (
    <TokenGate>
      <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--lc-bg)", fontFamily: "var(--font-ui)" }}>
        <AppHeader />
        <ErrorBanner />
        <main style={{ flex: 1, padding: "var(--space-3)", color: "var(--lc-text)", display: "flex", flexDirection: "column", gap: "var(--space-3)", minHeight: 0 }}>
          {session === null ? <HomeScreen onConnected={(s) => useSession.getState().setSession(s)} /> : <InstrumentShell />}
        </main>
      </div>
    </TokenGate>
  );
}
