import { useState } from "react";
import { AnalysisPanel } from "../controls/AnalysisPanel";
import { ChannelsPanel } from "../controls/ChannelsPanel";
import { MathPanel } from "../controls/MathPanel";
import { ScopeToolbar } from "../controls/ScopeToolbar";
import { TriggerPanel } from "../controls/TriggerPanel";
import { MeasurePanel } from "../measure/MeasurePanel";
import { ReferencePanel } from "../reference/ReferencePanel";
import { useReferenceSeed } from "../reference/useReferenceSeed";
import { LogPanel } from "../trend/LogPanel";
import { TrendCanvas } from "../trend/TrendCanvas";
import { SpectrumCanvas } from "../waveform/SpectrumCanvas";
import { WaveformCanvas } from "../waveform/WaveformCanvas";
import type { ViewMode } from "../waveform/ViewModeToggle";
import { ViewModeToggle } from "../waveform/ViewModeToggle";
import { Tabs } from "../../ds/Tabs";
import { useSession } from "../../store/session";

const RAIL_TABS = ["Channels", "Trigger", "Math", "Analysis", "Reference", "Log", "Measure"];

/** Everything below the readout strip for an oscilloscope session: the control
 *  rail and the canvas. Only this component knows a scope has a rail -- the
 *  shell imposes no layout on a kind. */
export function ScopeBody() {
  const sessionId = useSession((s) => s.session?.id ?? null);
  const [railTab, setRailTab] = useState("Channels");
  const [viewMode, setViewMode] = useState<ViewMode>("Time");
  // The kind guard this call used to carry in App.tsx is gone: /scope/reference
  // is behind require_kind, and only a scope session renders this component.
  useReferenceSeed(sessionId);
  return (
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
        </Tabs>
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "var(--space-3)", minWidth: 0 }}>
        {viewMode === "Time" ? <WaveformCanvas /> : viewMode === "Spectrum" ? <SpectrumCanvas /> : <TrendCanvas />}
        <ScopeToolbar viewToggle={<ViewModeToggle value={viewMode} onChange={setViewMode} />} />
      </div>
    </div>
  );
}
