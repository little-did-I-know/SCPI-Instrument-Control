import type { DiscoveredDevice } from "../../api/types";
import { Button } from "../../ds/Button";
import { kindMeta } from "./kinds";

export type DeviceCardProps = {
  device: DiscoveredDevice;
  variant: "available" | "session";
  busy?: boolean;
  onConnect: (device: DiscoveredDevice) => void;
  onOpen: (device: DiscoveredDevice) => void;
};

export function DeviceCard({ device, variant, busy = false, onConnect, onOpen }: DeviceCardProps) {
  const meta = kindMeta(device.kind);
  const viewers = device.viewers ?? 0;

  let action: React.ReactNode;
  if (device.connected) {
    action = (
      <Button size="sm" variant="primary" disabled={busy} aria-label={`Open ${device.model}`} onClick={() => onOpen(device)}>
        Open
      </Button>
    );
  } else if (meta.connectable) {
    action = (
      <Button size="sm" variant="primary" disabled={busy} aria-label={`Connect ${device.model}`} onClick={() => onConnect(device)}>
        Connect
      </Button>
    );
  } else {
    action = <span style={{ fontSize: "var(--text-xs)", color: "var(--lc-muted)" }}>Viewer coming soon</span>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)", border: "1px solid var(--lc-border)", borderRadius: "var(--lc-radius-sm)", background: "var(--lc-panel)", padding: "var(--space-2)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <span style={{ width: 4, height: 26, borderRadius: 2, background: meta.accent }} />
        <strong style={{ color: "var(--lc-text)" }}>{device.model}</strong>
        {variant === "session" && (
          <span style={{ marginLeft: "auto", fontSize: "var(--text-2xs)", color: "var(--success)", border: "1px solid var(--lc-border)", borderRadius: "var(--radius-pill)", padding: "1px 7px" }}>
            in use{viewers > 0 ? ` · ${viewers} viewer${viewers === 1 ? "" : "s"}` : ""}
          </span>
        )}
      </div>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--lc-muted)" }}>
        {meta.label}
        {device.address ? ` · ${device.address}` : ""}
        {device.dialect ? ` · ${device.dialect}` : ""}
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>{action}</div>
    </div>
  );
}
