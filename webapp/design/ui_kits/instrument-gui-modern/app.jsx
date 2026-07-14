// Instrument Control GUI — CONSOLE (light, default modern shell).
// A bright, elevated lab interface. The dark scope canvas stays as the
// "instrument window"; the chrome is light, modern, with channel-colour
// accents and a standout live-readout strip.
// Reuses design-system Button / StatusIndicator / DataTable / Terminal.
const NS = window.SCPIInstrumentControlDesignSystem_b228f5;
const { Button, StatusIndicator, DataTable, Terminal } = NS;

const TRACE = { 1: "#E0A800", 2: "#0F9FB0", 3: "#E01A7F", 4: "#1FA83B" }; // ink-legible channel accents on light
const DOT = { 1: "#FFDC32", 2: "#40E0D0", 3: "#FF69B4", 4: "#32FF64" };   // vibrant swatch (matches trace on canvas)
const COUPLING = ["DC", "AC", "GND"];
const PROBES = ["0.1X", "1X", "10X", "100X", "1000X"];

const DEFAULTS = [
  { num: 1, enabled: true,  vdiv: 1.0, coupling: "DC", offset: 0,  freq: 3, amp: 0.70, phase: 0.0, shape: "sine" },
  { num: 2, enabled: true,  vdiv: 0.5, coupling: "AC", offset: -2, freq: 5, amp: 0.50, phase: 1.0, shape: "sine" },
  { num: 3, enabled: false, vdiv: 2.0, coupling: "DC", offset: 2,  freq: 2, amp: 0.60, phase: 0.5, shape: "square" },
  { num: 4, enabled: false, vdiv: 1.0, coupling: "DC", offset: -3, freq: 4, amp: 0.40, phase: 2.0, shape: "triangle" },
];

const S = {
  shell: { display: "flex", flexDirection: "column", height: "100vh", background: "var(--lc-bg)",
           color: "var(--lc-text)", fontFamily: "var(--font-ui)" },
  panel: { background: "var(--lc-panel)", border: "1px solid var(--lc-border)",
           borderRadius: "var(--lc-radius)", boxShadow: "var(--lc-elev-1)" },
  cap: { fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--lc-muted)",
         display: "block", marginBottom: 4 },
};

// ---- Light form controls (console-styled) ----
function LSelect({ options, value, onChange, width }) {
  const norm = options.map((o) => (typeof o === "string" ? { label: o, value: o } : o));
  return (
    <div style={{ position: "relative", width: width || "100%" }}>
      <select value={value} onChange={(e) => onChange && onChange(e.target.value)}
        style={{ appearance: "none", WebkitAppearance: "none", width: "100%", height: 32,
          padding: "0 26px 0 10px", fontFamily: "var(--font-ui)", fontSize: 13, color: "var(--lc-text)",
          background: "var(--lc-control)", border: "1px solid var(--lc-border-strong)",
          borderRadius: "var(--lc-radius-sm)", cursor: "pointer", outline: "none" }}>
        {norm.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <span style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
        pointerEvents: "none", color: "var(--lc-muted)", fontSize: 10 }}>▾</span>
    </div>
  );
}
function LSpin({ value, min, max, step = 0.1, decimals = 3, suffix = "", onChange, width }) {
  const clamp = (v) => Math.min(max ?? Infinity, Math.max(min ?? -Infinity, v));
  const [foc, setFoc] = React.useState(false);
  const nudge = (d) => onChange && onChange(clamp(value + d * step));
  return (
    <div style={{ display: "flex", height: 32, width: width || "100%", background: "var(--lc-control)",
      border: `1px solid ${foc ? "var(--lc-accent)" : "var(--lc-border-strong)"}`,
      borderRadius: "var(--lc-radius-sm)", overflow: "hidden",
      boxShadow: foc ? "0 0 0 3px var(--lc-accent-soft)" : "none" }}>
      <input value={value.toFixed(decimals) + suffix} onFocus={() => setFoc(true)}
        onBlur={(e) => { setFoc(false); const n = parseFloat(e.target.value); if (!isNaN(n)) onChange && onChange(clamp(n)); }}
        onChange={() => {}} readOnly
        style={{ flex: 1, minWidth: 0, border: "none", outline: "none", background: "transparent",
          padding: "0 10px", fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--lc-text)" }} />
      <div style={{ display: "flex", flexDirection: "column", width: 20, borderLeft: "1px solid var(--lc-border)" }}>
        <button onClick={() => nudge(1)} style={spinBtn}>▲</button>
        <button onClick={() => nudge(-1)} style={{ ...spinBtn, borderTop: "1px solid var(--lc-border)" }}>▼</button>
      </div>
    </div>
  );
}
const spinBtn = { flex: 1, border: "none", background: "var(--lc-panel-2)", color: "var(--lc-text-2)",
  cursor: "pointer", fontSize: 7, lineHeight: 1, padding: 0 };
function LCheck({ label, checked, onChange, accent }) {
  return (
    <label onClick={() => onChange && onChange(!checked)}
      style={{ display: "inline-flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, userSelect: "none" }}>
      <span style={{ width: 17, height: 17, borderRadius: 5, flexShrink: 0, display: "inline-flex",
        alignItems: "center", justifyContent: "center",
        background: checked ? (accent || "var(--lc-accent)") : "var(--lc-control)",
        border: `1px solid ${checked ? (accent || "var(--lc-accent)") : "var(--lc-border-strong)"}` }}>
        {checked && <svg width="11" height="11" viewBox="0 0 12 12"><path d="M2.5 6.2L4.8 8.5L9.5 3.5"
          stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>}
      </span>
      {label}
    </label>
  );
}

// ---- Standout live-readout strip ----
function ReadoutStrip({ channels, running, sampleRate }) {
  const active = channels.filter((c) => c.enabled);
  return (
    <div style={{ display: "flex", gap: 12, padding: "14px 16px 4px", alignItems: "stretch", flexWrap: "wrap" }}>
      {active.length === 0 && (
        <div style={{ ...S.panel, flex: 1, padding: "16px 18px", color: "var(--lc-muted)", fontSize: 13 }}>
          No active channels — enable a channel to see live measurements.
        </div>
      )}
      {active.map((c) => {
        const vpp = (c.amp * c.vdiv * 4).toFixed(2);
        const freq = (c.freq * 100).toFixed(1);
        return (
          <div key={c.num} style={{ ...S.panel, minWidth: 200, flex: "1 1 200px", padding: "14px 16px 14px 18px",
            position: "relative", overflow: "hidden", boxShadow: "var(--lc-elev-1)" }}>
            <span style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 5, background: DOT[c.num] }} />
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)",
                fontWeight: 700, fontSize: 12, color: TRACE[c.num] }}>
                <span style={{ width: 9, height: 9, borderRadius: 999, background: DOT[c.num] }} />C{c.num}
              </span>
              <span style={{ fontSize: 11, color: "var(--lc-muted)", fontFamily: "var(--font-mono)" }}>{c.coupling} · {c.vdiv} V/div</span>
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 7 }}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 32, fontWeight: 700, lineHeight: 1,
                color: "var(--lc-text)", letterSpacing: "-0.01em" }}>{running ? vpp : "--.--"}</span>
              <span style={{ fontSize: 13, color: "var(--lc-text-2)", fontWeight: 600 }}>Vpp</span>
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--lc-text-2)", marginTop: 5 }}>
              {running ? `${freq} kHz` : "—"}
            </div>
          </div>
        );
      })}
      <div style={{ ...S.panel, minWidth: 168, padding: "14px 16px", display: "flex", flexDirection: "column", justifyContent: "center", gap: 8 }}>
        <div><span style={S.cap}>Sample rate</span><span style={{ fontFamily: "var(--font-mono)", fontSize: 17, fontWeight: 600 }}>{sampleRate}</span></div>
        <div style={{ display: "flex", gap: 18 }}>
          <div><span style={S.cap}>FPS</span><span style={{ fontFamily: "var(--font-mono)", fontSize: 17, fontWeight: 600, color: running ? "#1FA83B" : "var(--lc-muted)" }}>{running ? 45 : 0}</span></div>
          <div><span style={S.cap}>Mem</span><span style={{ fontFamily: "var(--font-mono)", fontSize: 17, fontWeight: 600 }}>14 Mpts</span></div>
        </div>
      </div>
    </div>
  );
}

function TabStrip({ tabs, value, onChange }) {
  return (
    <div style={{ display: "flex", gap: 3, padding: 4, background: "var(--lc-panel-2)",
      borderRadius: "var(--lc-radius)", border: "1px solid var(--lc-border)" }}>
      {tabs.map((t) => {
        const on = t === value;
        return (
          <button key={t} onClick={() => onChange(t)}
            style={{ flex: 1, border: "none", cursor: "pointer", fontFamily: "var(--font-ui)", fontSize: 13,
              fontWeight: on ? 600 : 500, padding: "8px 6px", borderRadius: "var(--lc-radius-sm)",
              color: on ? "var(--lc-text)" : "var(--lc-text-2)",
              background: on ? "var(--lc-panel)" : "transparent",
              boxShadow: on ? "var(--lc-elev-1)" : "none" }}>{t}</button>
        );
      })}
    </div>
  );
}

function ChannelCard({ c, update }) {
  return (
    <div style={{ ...S.panel, background: "var(--lc-panel)", padding: 0, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "11px 13px", borderBottom: "1px solid var(--lc-divider)",
        borderLeft: `4px solid ${DOT[c.num]}` }}>
        <LCheck label={<b style={{ color: TRACE[c.num] }}>Channel {c.num}</b>} checked={c.enabled}
          accent={DOT[c.num]} onChange={(v) => update(c.num, { enabled: v })} />
        <Button size="sm">Auto Scale</Button>
      </div>
      <div style={{ padding: 13, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 11,
        opacity: c.enabled ? 1 : 0.5 }}>
        <label style={S.cap}>V/div<LSpin value={c.vdiv} min={0.001} max={10} suffix=" V" onChange={(v) => update(c.num, { vdiv: v })} /></label>
        <label style={S.cap}>Offset<LSpin value={c.offset} min={-10} max={10} suffix=" V" onChange={(v) => update(c.num, { offset: v })} /></label>
        <label style={S.cap}>Coupling<LSelect options={COUPLING} value={c.coupling} onChange={(v) => update(c.num, { coupling: v })} /></label>
        <label style={S.cap}>Probe<LSelect options={PROBES} value="10X" onChange={() => {}} /></label>
      </div>
    </div>
  );
}

function AppConsole() {
  const [conn, setConn] = React.useState("disconnected");
  const [running, setRunning] = React.useState(false);
  const [showGrid, setShowGrid] = React.useState(true);
  const [tab, setTab] = React.useState("Channels");
  const [channels, setChannels] = React.useState(DEFAULTS);
  const [term, setTerm] = React.useState([]);
  const connected = conn === "connected";
  const update = (num, patch) => setChannels((cs) => cs.map((c) => (c.num === num ? { ...c, ...patch } : c)));

  const connect = () => {
    if (conn !== "disconnected") return;
    setConn("connecting");
    setTimeout(() => { setConn("connected"); setRunning(true);
      setTerm((t) => [...t, { text: "=== Oscilloscope Connected ===", kind: "ok" },
        { text: "> *IDN?", kind: "command" }, { text: "  Siglent,SDS824X HD,SN12345,1.2.3.4", kind: "response" }]);
    }, 900);
  };
  const disconnect = () => { setConn("disconnected"); setRunning(false); };
  const sendCmd = (cmd) => setTerm((t) => [...t, { text: `> ${cmd}`, kind: "command" },
    cmd.includes("?") ? { text: "  1.000E+00", kind: "response" } : { text: "  OK", kind: "ok" }]);

  const measRows = channels.filter((c) => c.enabled).flatMap((c) => [
    [<span style={{ color: TRACE[c.num], fontWeight: 700 }}>C{c.num}</span>, "Frequency", `${(c.freq * 100).toFixed(1)} kHz`],
    [<span style={{ color: TRACE[c.num], fontWeight: 700 }}>C{c.num}</span>, "Peak-to-Peak", `${(c.amp * c.vdiv * 4).toFixed(3)} V`],
    [<span style={{ color: TRACE[c.num], fontWeight: 700 }}>C{c.num}</span>, "RMS", `${(c.amp * c.vdiv * 1.41).toFixed(3)} V`],
  ]);

  return (
    <div style={S.shell}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "12px 18px",
        background: "var(--lc-panel)", borderBottom: "1px solid var(--lc-border)", boxShadow: "var(--lc-elev-1)", zIndex: 2 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
          <div style={{ width: 32, height: 32, borderRadius: 9, border: "1.5px solid var(--lc-text)",
            display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-mono)", fontSize: 17 }}>〜</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, lineHeight: 1.1 }}>SCPI Instrument Control</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--lc-muted)" }}>SDS824X HD · 192.168.1.100:5024</div>
          </div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ padding: "6px 13px", borderRadius: 999, background: "var(--lc-panel-2)",
            border: "1px solid var(--lc-border)" }}>
            <StatusIndicator state={conn} label={connected ? "Connected" : conn === "connecting" ? "Connecting…" : "Offline"} />
          </div>
          <Button variant="primary" onClick={connect} disabled={conn !== "disconnected"}>Connect</Button>
          <Button variant="danger" onClick={disconnect} disabled={!connected}>Disconnect</Button>
        </div>
      </div>

      {/* Standout readout strip */}
      <ReadoutStrip channels={connected ? channels : []} running={running && connected} sampleRate={connected ? "2 GSa/s" : "—"} />

      {/* Body */}
      <div style={{ display: "flex", flex: 1, minHeight: 0, gap: 14, padding: "10px 16px 16px" }}>
        {/* Left rail */}
        <div style={{ width: 380, flexShrink: 0, display: "flex", flexDirection: "column", gap: 12, minHeight: 0 }}>
          <TabStrip tabs={["Channels", "Trigger", "Measure", "Terminal"]} value={tab} onChange={setTab} />
          <div style={{ ...S.panel, flex: 1, padding: 13, overflowY: "auto", opacity: connected ? 1 : 0.55,
            pointerEvents: connected ? "auto" : "none" }}>
            {tab === "Channels" && <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>{channels.map((c) => <ChannelCard key={c.num} c={c} update={update} />)}</div>}
            {tab === "Trigger" && (
              <div style={{ display: "grid", gap: 12 }}>
                <label style={S.cap}>Mode<LSelect options={["AUTO", "NORMAL", "SINGLE", "STOP"]} value="AUTO" onChange={() => {}} /></label>
                <label style={S.cap}>Source<LSelect options={["C1", "C2", "C3", "C4", "EX", "LINE"]} value="C1" onChange={() => {}} /></label>
                <label style={S.cap}>Slope<LSelect options={["POS", "NEG"]} value="POS" onChange={() => {}} /></label>
                <label style={S.cap}>Level<LSpin value={0} min={-10} max={10} suffix=" V" onChange={() => {}} /></label>
                <div style={{ display: "flex", gap: 8, marginTop: 2 }}><Button fullWidth>Force Trigger</Button><Button fullWidth>Set 50%</Button></div>
              </div>
            )}
            {tab === "Measure" && (measRows.length
              ? <DataTable columns={["Ch", "Measurement", { label: "Value", align: "right", mono: true }]} rows={measRows} />
              : <div style={{ fontSize: 13, color: "var(--lc-muted)" }}>Enable a channel to see measurements.</div>)}
            {tab === "Terminal" && <div style={{ height: 440 }}><Terminal lines={term} onSend={sendCmd} style={{ height: "100%" }} /></div>}
          </div>
        </div>

        {/* Display — dark scope canvas framed as the instrument window */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>
          <div style={{ ...S.panel, flex: 1, overflow: "hidden", minHeight: 0, padding: 6, boxShadow: "var(--lc-elev-2)" }}>
            <div style={{ height: "100%", borderRadius: "calc(var(--lc-radius) - 4px)", overflow: "hidden" }}>
              <window.WaveformCanvas channels={connected ? channels : []} running={running && connected} showGrid={showGrid} />
            </div>
          </div>
          <div style={{ ...S.panel, display: "flex", alignItems: "center", gap: 14, padding: "9px 13px" }}>
            <div style={{ display: "flex", gap: 8 }}>
              {channels.filter((c) => c.enabled).map((c) => (
                <span key={c.num} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)",
                  fontSize: 12, padding: "4px 9px", borderRadius: 999, background: "var(--lc-panel-2)", border: "1px solid var(--lc-border)" }}>
                  <span style={{ width: 8, height: 8, borderRadius: 999, background: DOT[c.num] }} />C{c.num}
                </span>
              ))}
            </div>
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
              <LCheck label="Grid" checked={showGrid} onChange={setShowGrid} />
              <Button variant="ghost" size="sm" onClick={() => connected && setRunning(true)}>Run</Button>
              <Button variant="ghost" size="sm" onClick={() => setRunning(false)}>Stop</Button>
              <Button variant="ghost" size="sm">Export</Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
window.AppConsole = AppConsole;
