import { useState } from "react";
import { Button } from "../../ds/Button";
import { KIND_META, KIND_ORDER, type Kind } from "./kinds";

type Props = { busy: boolean; onConnectAddress: (address: string) => void; onConnectMock: (kind: Kind) => void };

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
      {/* One button per connectable kind in KIND_META, not a hardcoded pair:
          discovery finds nothing on a bench with no instruments, and the
          address field can only make a scope, so this is the only route to a
          session of a given kind without hardware. A new connectable kind
          needs no change here — it just needs an entry in KIND_META. */}
      {KIND_ORDER.filter((kind) => KIND_META[kind].connectable).map((kind) => (
        <Button key={kind} disabled={busy} onClick={() => onConnectMock(kind)}>
          Mock {KIND_META[kind].label}
        </Button>
      ))}
    </div>
  );
}
