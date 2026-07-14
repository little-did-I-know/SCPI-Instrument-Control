import { useState } from "react";
import { Button } from "../../ds/Button";

type Props = { busy: boolean; onConnectAddress: (address: string) => void; onConnectMock: () => void };

export function ManualConnect({ busy, onConnectAddress, onConnectMock }: Props) {
  const [address, setAddress] = useState("");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <div style={{ display: "flex", gap: "var(--space-1)" }}>
        <input
          aria-label="IP address"
          value={address}
          onChange={(event) => setAddress(event.target.value)}
          placeholder="192.168.1.50"
          style={{ flex: 1, padding: "6px 8px", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", border: "1px solid var(--lc-border-strong)", borderRadius: "var(--lc-radius-sm)", background: "var(--lc-control)", color: "var(--lc-text)" }}
        />
        <Button variant="primary" disabled={busy || !address.trim()} onClick={() => onConnectAddress(address.trim())}>
          Connect
        </Button>
      </div>
      <Button disabled={busy} onClick={onConnectMock}>
        Mock scope
      </Button>
    </div>
  );
}
