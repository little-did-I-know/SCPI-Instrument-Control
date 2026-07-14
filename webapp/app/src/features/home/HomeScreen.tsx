import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../../api/client";
import type { DiscoveredDevice, SessionInfo } from "../../api/types";
import { GroupBox } from "../../ds/GroupBox";
import { GettingStarted } from "./GettingStarted";
import { Hero } from "./Hero";
import { InstrumentDashboard } from "./InstrumentDashboard";
import { ManualConnect } from "./ManualConnect";
import { RecentBar } from "./RecentBar";
import { pushRecent, type RecentEntry } from "./recent";

type Props = { onConnected: (session: SessionInfo) => void };

const REFRESH_MS = 30_000;

function sessionAsDevice(s: SessionInfo): DiscoveredDevice {
  return { address: s.address, idn: s.idn, manufacturer: s.idn.split(",")[0]?.trim() ?? "", model: s.model, dialect: s.dialect, kind: "scope", connected: true, session_id: s.id, viewers: s.viewers };
}

export function HomeScreen({ onConnected }: Props) {
  const [devices, setDevices] = useState<DiscoveredDevice[]>([]);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyAddress, setBusyAddress] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastScanned, setLastScanned] = useState<string>("not scanned yet");
  const busyRef = useRef(false);

  const scan = useCallback(async () => {
    setScanning(true);
    setError(null);
    try {
      const sessions = await api.listSessions();
      const heldSeed = sessions.map(sessionAsDevice); // ALL held sessions, real + mock
      const heldAddrs = new Set(sessions.map((s) => s.address).filter((a): a is string => a !== null));
      // seed the sessions zone immediately, before the slow discover scan resolves
      setDevices((prev) => {
        // keep the prior available fleet, minus anything now held; prepend the held seed
        const priorFleet = prev.filter((d) => !d.connected && !heldAddrs.has(d.address ?? ""));
        return [...heldSeed, ...priorFleet];
      });
      const found = await api.discover();
      const foundHeld = new Set(found.filter((d) => d.connected).map((d) => d.address));
      const heldFromSessions = sessions.filter((s) => !foundHeld.has(s.address)).map(sessionAsDevice);
      setDevices([...heldFromSessions, ...found]);
      setLastScanned("last scanned just now");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setScanning(false);
    }
  }, []);

  useEffect(() => {
    scan();
    const id = setInterval(() => {
      if (!busyRef.current) scan();
    }, REFRESH_MS);
    return () => clearInterval(id);
  }, [scan]);

  async function connect(body: Parameters<typeof api.createSession>[0], recent: RecentEntry, address: string | null) {
    setBusy(true);
    busyRef.current = true;
    setBusyAddress(address);
    setActionError(null);
    try {
      const session = await api.createSession(body);
      pushRecent(recent);
      onConnected(session);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
      busyRef.current = false;
      setBusyAddress(null);
    }
  }

  const onConnectDevice = (d: DiscoveredDevice) => connect({ address: d.address ?? undefined, label: d.model }, { address: d.address, label: d.model, kind: d.kind, model: d.model, mock: false }, d.address);
  const onOpenDevice = async (d: DiscoveredDevice) => {
    if (!d.session_id) return;
    setBusy(true);
    busyRef.current = true;
    setBusyAddress(d.address);
    setActionError(null);
    try {
      const session = await api.getSession(d.session_id);
      pushRecent({ address: d.address, label: d.model, kind: d.kind, model: d.model, mock: false });
      onConnected(session);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
      busyRef.current = false;
      setBusyAddress(null);
    }
  };
  const onReconnect = (e: RecentEntry) => (e.mock ? connect({ mock: true }, e, null) : connect({ address: e.address ?? undefined, label: e.label }, e, e.address));
  const onConnectAddress = (address: string) => connect({ address, label: address }, { address, label: address, kind: "scope", model: address, mock: false }, address);
  const onConnectMock = () => connect({ mock: true }, { address: null, label: "Mock scope", kind: "scope", model: "Mock", mock: true }, null);

  return (
    <div>
      <Hero scanning={scanning} lastScannedLabel={lastScanned} onScan={scan} />
      <div style={{ display: "flex", gap: "var(--space-3)", padding: "var(--space-3)", alignItems: "flex-start" }}>
        <div style={{ flex: 3, display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          <RecentBar onReconnect={onReconnect} />
          {actionError && <div role="alert" style={{ padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>{actionError}</div>}
          <InstrumentDashboard devices={devices} scanning={scanning} error={error} busyAddress={busyAddress} onConnect={onConnectDevice} onOpen={onOpenDevice} />
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "var(--space-2)", minWidth: 220 }}>
          <GroupBox title="Connect manually"><ManualConnect busy={busy} onConnectAddress={onConnectAddress} onConnectMock={onConnectMock} /></GroupBox>
          <GroupBox title="Help"><GettingStarted /></GroupBox>
        </div>
      </div>
    </div>
  );
}
