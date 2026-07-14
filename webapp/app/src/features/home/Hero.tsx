import { Button } from "../../ds/Button";

type Props = { scanning: boolean; lastScannedLabel: string; onScan: () => void };

export function Hero({ scanning, lastScannedLabel, onScan }: Props) {
  return (
    <header style={{ background: "linear-gradient(180deg, var(--lc-panel), var(--lc-bg))", borderBottom: "1px solid var(--lc-border)", padding: "22px 16px", textAlign: "center" }}>
      <div style={{ fontSize: "var(--text-2xs)", color: "var(--success)" }}>● gateway online</div>
      <div style={{ fontSize: "var(--text-xl)", fontWeight: 700, color: "var(--lc-text)" }}>〜 SCPI Instrument Control</div>
      <div style={{ fontSize: "var(--text-sm)", color: "var(--lc-muted)", margin: "5px 0 12px" }}>Control bench instruments from any browser on the LAN</div>
      <Button variant="primary" disabled={scanning} aria-label="Scan network" onClick={onScan}>
        {scanning ? "Scanning…" : "⌕ Scan network"}
      </Button>
      <div style={{ fontSize: "var(--text-2xs)", color: "var(--lc-muted)", marginTop: 7 }}>{lastScannedLabel}</div>
    </header>
  );
}
