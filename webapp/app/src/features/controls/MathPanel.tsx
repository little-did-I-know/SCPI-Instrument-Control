import { useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import { GroupBox } from "../../ds/GroupBox";
import { useSession } from "../../store/session";

type MathState = { n: number; expression: string; enabled: boolean };

export function MathPanel() {
  const session = useSession((s) => s.session);
  const [math, setMath] = useState<MathState[]>([]);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.getMath(session.id).then((state) => {
      setMath(state);
      setDrafts(Object.fromEntries(state.map((m) => [m.n, m.expression])));
    }).catch(() => setMath([{ n: 1, expression: "", enabled: false }, { n: 2, expression: "", enabled: false }]));
  }, [session]);

  async function patch(n: number, body: { expression?: string; enabled?: boolean }) {
    if (!session) return;
    setError(null);
    try {
      setMath(await api.patchMath(session.id, n, body));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      {math.map((m) => (
        <GroupBox key={m.n} title={`Math ${m.n}`}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-sm)", color: "var(--lc-text)" }}>
              <input type="checkbox" aria-label={`Enable math ${m.n}`} checked={m.enabled} onChange={(e) => patch(m.n, { enabled: e.target.checked })} />
              Enabled
            </label>
            <input
              aria-label={`Math ${m.n} expression`}
              value={drafts[m.n] ?? ""}
              placeholder="e.g. C1 - C2, INTG(C1)"
              onChange={(e) => setDrafts((d) => ({ ...d, [m.n]: e.target.value }))}
              onBlur={(e) => e.target.value.trim() && e.target.value !== m.expression && patch(m.n, { expression: e.target.value.trim() })}
              style={{ padding: "6px 8px", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", border: "1px solid var(--lc-border-strong)", borderRadius: "var(--lc-radius-sm)", background: "var(--lc-control)", color: "var(--lc-text)" }}
            />
          </div>
        </GroupBox>
      ))}
      {error && <div role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)" }}>{error}</div>}
    </div>
  );
}
