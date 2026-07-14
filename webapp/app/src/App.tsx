import { useState } from "react";
import { ConnectDialog } from "./features/connect/ConnectDialog";
import { ChannelsPanel } from "./features/controls/ChannelsPanel";
import { ScopeToolbar } from "./features/controls/ScopeToolbar";
import { TriggerPanel } from "./features/controls/TriggerPanel";
import { MeasurePanel } from "./features/measure/MeasurePanel";
import { TerminalPanel } from "./features/terminal/TerminalPanel";
import { WaveformCanvas } from "./features/waveform/WaveformCanvas";
import { StatusIndicator } from "./ds/StatusIndicator";
import { Tabs } from "./ds/Tabs";
import { useStream } from "./stream/useStream";
import { useSession } from "./store/session";

const RAIL_TABS = ["Channels", "Trigger", "Measure", "Terminal"];

export default function App() {
  const status = useSession((s) => s.status);
  const session = useSession((s) => s.session);
  const [railTab, setRailTab] = useState("Channels");
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
        {session !== null && (
          <div style={{ flex: 1, display: "flex", gap: "var(--space-3)", minHeight: 0 }}>
            <div style={{ width: "280px", flexShrink: 0, overflowY: "auto" }}>
              <Tabs tabs={RAIL_TABS} value={railTab} onChange={setRailTab}>
                {railTab === "Channels" && <ChannelsPanel />}
                {railTab === "Trigger" && <TriggerPanel />}
                {railTab === "Measure" && <MeasurePanel />}
                {railTab === "Terminal" && <TerminalPanel />}
              </Tabs>
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "var(--space-3)", minWidth: 0 }}>
              <WaveformCanvas />
              <ScopeToolbar />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
