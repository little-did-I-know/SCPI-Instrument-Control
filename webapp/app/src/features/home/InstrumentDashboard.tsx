import { useState } from "react";
import type { DiscoveredDevice } from "../../api/types";
import { DeviceCard } from "./DeviceCard";
import { deviceKey } from "./deviceKey";
import { KIND_META, KIND_ORDER, type Kind } from "./kinds";

export type DashboardProps = {
  devices: DiscoveredDevice[];
  scanning: boolean;
  error: string | null;
  busyKey: string | null;
  onConnect: (device: DiscoveredDevice) => void;
  onOpen: (device: DiscoveredDevice) => void;
};

const zoneHeading = { fontSize: "var(--text-xs)", textTransform: "uppercase" as const, letterSpacing: "0.05em", color: "var(--lc-text-2)", fontWeight: 700, margin: "0 0 var(--space-2)" };
const grid = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "var(--space-2)" };

export function InstrumentDashboard({ devices, scanning, error, busyKey, onConnect, onOpen }: DashboardProps) {
  const [query, setQuery] = useState("");
  const held = devices.filter((d) => d.connected);
  const available = devices.filter((d) => !d.connected);

  const q = query.trim().toLowerCase();
  const filtered = q ? available.filter((d) => `${d.model} ${d.address ?? ""} ${d.kind}`.toLowerCase().includes(q)) : available;

  function cardFor(device: DiscoveredDevice, variant: "available" | "session") {
    return <DeviceCard key={deviceKey(device)} device={device} variant={variant} busy={busyKey !== null && busyKey === deviceKey(device)} onConnect={onConnect} onOpen={onOpen} />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      {held.length > 0 && (
        <section>
          <h2 style={zoneHeading}>● Your sessions <span style={{ color: "var(--lc-muted)" }}>{held.length}</span></h2>
          <div style={grid}>{held.map((d) => cardFor(d, "session"))}</div>
        </section>
      )}

      <section>
        <h2 style={zoneHeading}>Available on the network <span style={{ color: "var(--lc-muted)" }}>{q ? `${filtered.length} of ${available.length}` : available.length}</span></h2>
        <input
          aria-label="Filter instruments"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="filter by model, IP, or type…"
          style={{ width: "100%", boxSizing: "border-box", padding: "6px 9px", marginBottom: "var(--space-2)", border: "1px solid var(--lc-border)", borderRadius: "var(--lc-radius-sm)", background: "var(--lc-control)", color: "var(--lc-text)", fontSize: "var(--text-sm)" }}
        />

        {scanning && devices.length === 0 && <p style={{ color: "var(--lc-muted)" }}>Scanning your network…</p>}
        {error && <p role="alert" style={{ color: "var(--danger)" }}>{error}</p>}
        {!scanning && !error && devices.length === 0 && (
          <p style={{ color: "var(--lc-muted)" }}>No instruments found on your network. Check the instrument's LAN settings, enter an IP manually, or start a Mock scope.</p>
        )}
        {q && filtered.length === 0 && available.length > 0 && <p style={{ color: "var(--lc-muted)" }}>No instruments match &ldquo;{query.trim()}&rdquo;.</p>}

        {KIND_ORDER.map((kind: Kind) => {
          const inKind = filtered.filter((d) => (d.kind as Kind) === kind || (kind === "unknown" && !(d.kind in KIND_META)));
          if (inKind.length === 0) return null;
          return (
            <div key={kind} style={{ marginBottom: "var(--space-3)" }}>
              <div style={{ fontSize: "var(--text-2xs)", textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--lc-muted)", fontWeight: 700, margin: "var(--space-2) 0" }}>
                {KIND_META[kind].plural} · {inKind.length}
              </div>
              <div style={grid}>{inKind.map((d) => cardFor(d, "available"))}</div>
            </div>
          );
        })}
      </section>
    </div>
  );
}
