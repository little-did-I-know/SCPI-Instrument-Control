import { useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import type { ReferenceInfo } from "../../api/types";
import { Button } from "../../ds/Button";
import { GroupBox } from "../../ds/GroupBox";
import { useSession } from "../../store/session";

const inputStyle = { padding: "6px 8px", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", border: "1px solid var(--lc-border-strong)", borderRadius: "var(--lc-radius-sm)", background: "var(--lc-control)", color: "var(--lc-text)", minWidth: 0, flex: 1 } as const;
const rowStyle = { display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-sm)", color: "var(--lc-text)" } as const;

export function ReferencePanel() {
  const session = useSession((s) => s.session);
  const activeReference = useSession((s) => s.activeReference);
  const referenceStats = useSession((s) => s.referenceStats);
  const [refs, setRefs] = useState<ReferenceInfo[]>([]);
  const [name, setName] = useState("");
  const [channel, setChannel] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const channels = Array.from({ length: session?.num_channels ?? 4 }, (_, i) => i + 1);

  useEffect(() => {
    if (!session) return;
    api.listReferences(session.id).then(setRefs).catch(() => {});
  }, [session]);

  async function guard<T>(fn: () => Promise<T>): Promise<T | null> {
    setError(null);
    try {
      return await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
      return null;
    }
  }

  async function save() {
    if (!session || !name.trim()) return;
    const updated = await guard(() => api.saveReference(session.id, name.trim(), channel));
    if (updated) {
      setRefs(updated);
      setName("");
    }
  }

  async function toggleActive(ref: ReferenceInfo) {
    if (!session) return;
    const next = activeReference?.name === ref.name ? null : ref.name;
    await guard(() => api.putReference(session.id, next));
    // overlay + store update arrive via the stream broadcast — no local apply
  }

  async function remove(refName: string) {
    if (!session) return;
    const deleted = await guard(() => api.deleteReference(session.id, refName));
    if (deleted !== null) {
      const updated = await guard(() => api.listReferences(session.id));
      if (updated) setRefs(updated);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <GroupBox title="Save reference">
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <input aria-label="Reference name" placeholder="name" value={name} onChange={(e) => setName(e.target.value)} style={inputStyle} />
          <label style={rowStyle}>
            Channel
            <select aria-label="Reference channel" value={channel} onChange={(e) => setChannel(Number(e.target.value))} style={inputStyle}>
              {channels.map((c) => (<option key={c} value={c}>C{c}</option>))}
            </select>
          </label>
          <Button onClick={save}>Save reference</Button>
        </div>
      </GroupBox>
      <GroupBox title="Saved references">
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          {refs.length === 0 && <span style={{ color: "var(--lc-muted)", fontSize: "var(--text-sm)" }}>No saved references</span>}
          {refs.map((ref) => {
            const active = activeReference?.name === ref.name;
            return (
              <div key={ref.name} style={rowStyle}>
                <span style={{ flex: 1, fontFamily: "var(--font-mono)", overflow: "hidden", textOverflow: "ellipsis" }}>{ref.name}</span>
                <span style={{ color: "var(--lc-muted)" }}>C{ref.channel ?? "?"}</span>
                <Button variant="ghost" aria-label={`${active ? "Deactivate" : "Activate"} ${ref.name}`} onClick={() => toggleActive(ref)}>
                  {active ? "Hide" : "Show"}
                </Button>
                <Button variant="ghost" aria-label={`Delete ${ref.name}`} onClick={() => remove(ref.name)}>
                  ✕
                </Button>
              </div>
            );
          })}
        </div>
      </GroupBox>
      {activeReference && (
        <GroupBox title="Comparison">
          <div style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "var(--text-sm)", color: "var(--lc-text)", fontFamily: "var(--font-mono)" }}>
            <span>vs {activeReference.name} (C{activeReference.channel ?? "?"})</span>
            <span>correlation: {referenceStats?.correlation != null ? referenceStats.correlation.toFixed(3) : "—"}</span>
            <span>max deviation: {referenceStats?.max_deviation != null ? `${referenceStats.max_deviation.toFixed(3)} V` : "—"}</span>
          </div>
        </GroupBox>
      )}
      {error && <div role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)" }}>{error}</div>}
    </div>
  );
}
