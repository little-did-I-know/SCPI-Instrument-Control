import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../../api/client";
import type { DiscoveredDevice, SessionInfo } from "../../api/types";
import { GroupBox } from "../../ds/GroupBox";
import { deviceKey } from "./deviceKey";
import { GettingStarted } from "./GettingStarted";
import { Hero } from "./Hero";
import { InstrumentDashboard } from "./InstrumentDashboard";
import { ManualConnect } from "./ManualConnect";
import { RecentBar } from "./RecentBar";
import { pushRecent, type RecentEntry } from "./recent";
import { asKind, kindMeta, type Kind } from "./kinds";
import { useIdentity } from "../../store/identity";

type Props = { onConnected: (session: SessionInfo) => void };

const REFRESH_MS = 30_000;

function sessionAsDevice(s: SessionInfo): DiscoveredDevice {
  // s.kind, not a hardcoded "scope": the dashboard groups devices by kind, so
  // hardcoding filed every live PSU session under "Oscilloscopes".
  return { address: s.address, idn: s.idn, manufacturer: s.idn.split(",")[0]?.trim() ?? "", model: s.model, dialect: s.dialect, kind: s.kind, connected: true, session_id: s.id, viewers: s.viewers };
}

export function HomeScreen({ onConnected }: Props) {
  const [devices, setDevices] = useState<DiscoveredDevice[]>([]);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastScanned, setLastScanned] = useState<string>("not scanned yet");
  const busyRef = useRef(false);
  const identity = useIdentity((s) => s.identity);

  const scan = useCallback(async () => {
    setScanning(true);
    setError(null);
    try {
      const sessions = await api.listSessions();
      setSessions(sessions);
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

  async function connect(body: Parameters<typeof api.createSession>[0], recent: RecentEntry, key: string | null) {
    setBusy(true);
    busyRef.current = true;
    setBusyKey(key);
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
      setBusyKey(null);
    }
  }

  // The kind discovery already determined has to travel with the create call:
  // without it the server defaults every session to "scope", so connecting to a
  // discovered SPD3303X builds an Oscilloscope against a power supply and is
  // refused by the session's kind guard.
  const onConnectDevice = (d: DiscoveredDevice) =>
    connect({ address: d.address ?? undefined, label: d.model, kind: asKind(d.kind) }, { address: d.address, label: d.model, kind: d.kind, model: d.model, mock: false }, deviceKey(d));
  const onOpenDevice = async (d: DiscoveredDevice) => {
    if (!d.session_id) return;
    setBusy(true);
    busyRef.current = true;
    setBusyKey(deviceKey(d));
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
      setBusyKey(null);
    }
  };
  // A recent entry records the kind it was connected as; replay it, or
  // reconnecting a remembered PSU would silently come back as a scope.
  const onReconnect = (e: RecentEntry) => (e.mock ? connect({ mock: true, kind: asKind(e.kind) }, e, null) : connect({ address: e.address ?? undefined, label: e.label, kind: asKind(e.kind) }, e, e.address));
  // Manual IP entry carries no discovery result, so it stays a scope — the
  // only kind a bare address can be assumed to be.
  const onConnectAddress = (address: string) => connect({ address, label: address, kind: "scope" }, { address, label: address, kind: "scope", model: address, mock: false }, address);
  // One handler for every connectable kind, not one prop per kind: the mock
  // button that calls this lives in ManualConnect, driven off KIND_META.
  const onConnectMock = (kind: Kind) => connect({ mock: true, kind }, { address: null, label: `Mock ${kindMeta(kind).label}`, kind, model: "Mock", mock: true }, null);

  return (
    <div>
      <Hero scanning={scanning} lastScannedLabel={lastScanned} onScan={scan} />
      <div style={{ display: "flex", gap: "var(--space-3)", padding: "var(--space-3)", alignItems: "flex-start" }}>
        <div style={{ flex: 3, display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          <RecentBar onReconnect={onReconnect} />
          {actionError && <div role="alert" style={{ padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>{actionError}</div>}
          <InstrumentDashboard devices={devices} scanning={scanning} error={error} busyKey={busyKey} onConnect={onConnectDevice} onOpen={onOpenDevice} sessions={sessions} identity={identity} onClaimed={scan} />
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "var(--space-2)", minWidth: 220 }}>
          <GroupBox title="Connect manually"><ManualConnect busy={busy} onConnectAddress={onConnectAddress} onConnectMock={onConnectMock} /></GroupBox>
          <GroupBox title="Help"><GettingStarted /></GroupBox>
        </div>
      </div>
    </div>
  );
}
