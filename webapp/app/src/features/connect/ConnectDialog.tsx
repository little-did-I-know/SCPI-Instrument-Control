import { useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import type { DiscoveredDevice, SessionInfo } from "../../api/types";
import { Button } from "../../ds/Button";
import { GroupBox } from "../../ds/GroupBox";

type Props = { onConnected: (session: SessionInfo) => void };

export function ConnectDialog({ onConnected }: Props) {
  const [devices, setDevices] = useState<DiscoveredDevice[]>([]);
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [existingSessions, setExistingSessions] = useState<SessionInfo[]>([]);

  useEffect(() => {
    api
      .listSessions()
      .then(setExistingSessions)
      .catch(() => setExistingSessions([]));
  }, []);

  async function scan() {
    setScanning(true);
    setError(null);
    try {
      setDevices(await api.discover());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setScanning(false);
    }
  }

  async function connect(body: Parameters<typeof api.createSession>[0]) {
    setBusy(true);
    setError(null);
    try {
      onConnected(await api.createSession(body));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 620, margin: "48px auto", display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      {existingSessions.length > 0 && (
        <GroupBox title="Resume a session">
          <table style={{ width: "100%", fontSize: "var(--text-sm)", borderCollapse: "collapse" }}>
            <tbody>
              {existingSessions.map((s) => (
                <tr key={s.id} style={{ borderTop: "1px solid var(--lc-border)" }}>
                  <td style={{ padding: "6px 4px" }}>{s.label}</td>
                  <td style={{ padding: "6px 4px" }}>{s.model}</td>
                  <td style={{ padding: "6px 4px", fontFamily: "var(--font-mono)", color: "var(--lc-muted)" }}>{s.address ?? "mock"}</td>
                  <td style={{ padding: "6px 4px", textAlign: "right" }}>
                    <Button size="sm" variant="primary" onClick={() => onConnected(s)}>
                      Resume
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </GroupBox>
      )}

      <GroupBox title="Find an instrument">
        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", marginBottom: "var(--space-3)" }}>
          <Button onClick={scan} disabled={scanning}>
            {scanning ? "Scanning…" : "Scan network"}
          </Button>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--lc-muted)" }}>Scans this machine's subnet on port 5025</span>
        </div>
        {devices.length > 0 && (
          <table style={{ width: "100%", fontSize: "var(--text-sm)", borderCollapse: "collapse" }}>
            <tbody>
              {devices.map((device) => (
                <tr key={device.address} style={{ borderTop: "1px solid var(--lc-border)" }}>
                  <td style={{ padding: "6px 4px", fontFamily: "var(--font-mono)" }}>{device.address}</td>
                  <td style={{ padding: "6px 4px" }}>{device.model}</td>
                  <td style={{ padding: "6px 4px", color: "var(--lc-muted)" }}>{device.dialect}</td>
                  <td style={{ padding: "6px 4px", textAlign: "right" }}>
                    {device.connected ? (
                      <span style={{ color: "var(--lc-muted)" }}>in use</span>
                    ) : (
                      <Button size="sm" variant="primary" disabled={busy} onClick={() => connect({ address: device.address, label: device.model })}>
                        Connect
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </GroupBox>

      <GroupBox title="Connect manually">
        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
          <input
            aria-label="IP address"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            placeholder="192.168.1.50"
            style={{ flex: 1, padding: "6px 8px", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", border: "1px solid var(--lc-border-strong)", borderRadius: "var(--lc-radius-sm)", background: "var(--lc-control)", color: "var(--lc-text)" }}
          />
          <Button
            aria-label="Connect manually"
            variant="primary"
            disabled={busy || !address.trim()}
            onClick={() => connect({ address: address.trim(), label: address.trim() })}
          >
            Connect
          </Button>
        </div>
      </GroupBox>

      <GroupBox title="No hardware?">
        <Button disabled={busy} onClick={() => connect({ mock: true })}>
          Mock scope
        </Button>
      </GroupBox>

      {error && (
        <div role="alert" style={{ padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {error}
        </div>
      )}
    </div>
  );
}
