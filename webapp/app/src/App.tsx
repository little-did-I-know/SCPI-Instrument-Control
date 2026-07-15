import { useState } from "react";
import { AnalysisPanel } from "./features/controls/AnalysisPanel";
import { ChannelsPanel } from "./features/controls/ChannelsPanel";
import { MathPanel } from "./features/controls/MathPanel";
import { ScopeToolbar } from "./features/controls/ScopeToolbar";
import { TriggerPanel } from "./features/controls/TriggerPanel";
import { HomeScreen } from "./features/home/HomeScreen";
import { MeasurePanel } from "./features/measure/MeasurePanel";
import { ReadoutStrip } from "./features/readout/ReadoutStrip";
import { ReferencePanel } from "./features/reference/ReferencePanel";
import { useReferenceSeed } from "./features/reference/useReferenceSeed";
import { TerminalPanel } from "./features/terminal/TerminalPanel";
import { LogPanel } from "./features/trend/LogPanel";
import { TrendCanvas } from "./features/trend/TrendCanvas";
import { SpectrumCanvas } from "./features/waveform/SpectrumCanvas";
import { WaveformCanvas } from "./features/waveform/WaveformCanvas";
import type { ViewMode } from "./features/waveform/ViewModeToggle";
import { ViewModeToggle } from "./features/waveform/ViewModeToggle";
import { StatusIndicator } from "./ds/StatusIndicator";
import { Tabs } from "./ds/Tabs";
import { useStream } from "./stream/useStream";
import { useSession } from "./store/session";

const RAIL_TABS = ["Channels", "Trigger", "Math", "Analysis", "Reference", "Log", "Measure", "Terminal"];

export default function App() {
  const status = useSession((s) => s.status);
  const session = useSession((s) => s.session);
  const [railTab, setRailTab] = useState("Channels");
  const [viewMode, setViewMode] = useState<ViewMode>("Time");
  useStream(session?.id ?? null);
  useReferenceSeed(session?.id ?? null);
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--lc-bg)", fontFamily: "var(--font-ui)" }}>
      <header style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", padding: "10px 14px", background: "var(--lc-panel)", borderBottom: "1px solid var(--lc-border)" }}>
        <strong style={{ color: "var(--lc-text)" }}>SCPI Instrument Control</strong>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--lc-muted)" }}>{session ? `${session.model} · ${session.address ?? "mock"}` : "no instrument"}</span>
        <span style={{ marginLeft: "auto" }}>
          <StatusIndicator state={status} />
        </span>
      </header>
      <main style={{ flex: 1, padding: "var(--space-3)", color: "var(--lc-text)", display: "flex", flexDirection: "column", gap: "var(--space-3)", minHeight: 0 }}>
        {session === null && <HomeScreen onConnected={(s) => useSession.getState().setSession(s)} />}
        {session !== null && <ReadoutStrip />}
        {session !== null && (
          <div style={{ flex: 1, display: "flex", gap: "var(--space-3)", minHeight: 0 }}>
            <div style={{ width: "280px", flexShrink: 0, overflowY: "auto" }}>
              <Tabs tabs={RAIL_TABS} value={railTab} onChange={setRailTab}>
                {railTab === "Channels" && <ChannelsPanel />}
                {railTab === "Trigger" && <TriggerPanel />}
                {railTab === "Math" && <MathPanel />}
                {railTab === "Analysis" && <AnalysisPanel />}
                {railTab === "Reference" && <ReferencePanel />}
                {railTab === "Log" && <LogPanel />}
                {railTab === "Measure" && <MeasurePanel />}
                {railTab === "Terminal" && <TerminalPanel />}
              </Tabs>
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "var(--space-3)", minWidth: 0 }}>
              {viewMode === "Time" ? <WaveformCanvas /> : viewMode === "Spectrum" ? <SpectrumCanvas /> : <TrendCanvas />}
              <ScopeToolbar viewToggle={<ViewModeToggle value={viewMode} onChange={setViewMode} />} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
