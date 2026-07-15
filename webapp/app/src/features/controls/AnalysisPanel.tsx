import { useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import type { FilterConfig, SpectrumConfig } from "../../api/types";
import { GroupBox } from "../../ds/GroupBox";
import { useSession } from "../../store/session";

const WINDOWS = ["rectangular", "hanning", "hamming", "blackman", "bartlett", "flattop"];
const KINDS: FilterConfig["kind"][] = ["lowpass", "highpass", "bandpass"];

const inputStyle = { padding: "6px 8px", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", border: "1px solid var(--lc-border-strong)", borderRadius: "var(--lc-radius-sm)", background: "var(--lc-control)", color: "var(--lc-text)", minWidth: 0, flex: 1 } as const;
const rowStyle = { display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-sm)", color: "var(--lc-text)" } as const;

export function AnalysisPanel() {
  const session = useSession((s) => s.session);
  const [spectrum, setSpectrumConfig] = useState<SpectrumConfig | null>(null);
  const [filters, setFilters] = useState<FilterConfig[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const channels = Array.from({ length: session?.num_channels ?? 4 }, (_, i) => i + 1);

  useEffect(() => {
    if (!session) return;
    api.getSpectrum(session.id).then(setSpectrumConfig).catch(() => {});
    api.getFilters(session.id).then((state) => {
      setFilters(state);
      setDrafts(Object.fromEntries(state.flatMap((f) => [
        [`low${f.n}`, f.cutoff_low?.toString() ?? ""],
        [`high${f.n}`, f.cutoff_high?.toString() ?? ""],
        [`order${f.n}`, String(f.order)],
      ])));
    }).catch(() => {});
  }, [session]);

  async function patchSpectrum(body: Partial<SpectrumConfig>) {
    if (!session) return;
    setError(null);
    try {
      setSpectrumConfig(await api.patchSpectrum(session.id, body));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  async function patchFilter(n: number, body: Partial<Omit<FilterConfig, "n">>) {
    if (!session) return;
    setError(null);
    try {
      setFilters(await api.patchFilter(session.id, n, body));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  function commitNumber(n: number, key: "cutoff_low" | "cutoff_high" | "order", raw: string) {
    const value = Number(raw);
    if (!raw.trim() || !Number.isFinite(value) || value <= 0) return;
    patchFilter(n, { [key]: value });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      {spectrum && (
        <GroupBox title="Spectrum">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            <label style={rowStyle}>
              <input type="checkbox" aria-label="Enable spectrum" checked={spectrum.enabled} onChange={(e) => patchSpectrum({ enabled: e.target.checked })} />
              Enabled
            </label>
            <label style={rowStyle}>
              Source
              <select aria-label="Spectrum source" value={spectrum.channel} onChange={(e) => patchSpectrum({ channel: Number(e.target.value) })} style={inputStyle}>
                {channels.map((c) => (<option key={c} value={c}>C{c}</option>))}
              </select>
            </label>
            <label style={rowStyle}>
              Window
              <select aria-label="Spectrum window" value={spectrum.window} onChange={(e) => patchSpectrum({ window: e.target.value })} style={inputStyle}>
                {WINDOWS.map((w) => (<option key={w} value={w}>{w}</option>))}
              </select>
            </label>
            <label style={rowStyle}>
              <input type="checkbox" aria-label="Magnitude in dB" checked={spectrum.db} onChange={(e) => patchSpectrum({ db: e.target.checked })} />
              Magnitude in dB
            </label>
          </div>
        </GroupBox>
      )}
      {filters.map((f) => (
        <GroupBox key={f.n} title={`Filter ${f.n} (F${f.n})`}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            <label style={rowStyle}>
              <input type="checkbox" aria-label={`Enable filter ${f.n}`} checked={f.enabled} onChange={(e) => patchFilter(f.n, { enabled: e.target.checked })} />
              Enabled
            </label>
            <label style={rowStyle}>
              Source
              <select aria-label={`Filter ${f.n} source`} value={f.source} onChange={(e) => patchFilter(f.n, { source: Number(e.target.value) })} style={inputStyle}>
                {channels.map((c) => (<option key={c} value={c}>C{c}</option>))}
              </select>
            </label>
            <label style={rowStyle}>
              Kind
              <select aria-label={`Filter ${f.n} kind`} value={f.kind} onChange={(e) => patchFilter(f.n, { kind: e.target.value as FilterConfig["kind"] })} style={inputStyle}>
                {KINDS.map((k) => (<option key={k} value={k}>{k}</option>))}
              </select>
            </label>
            {f.kind !== "lowpass" && (
              <label style={rowStyle}>
                Low (Hz)
                <input aria-label={`Filter ${f.n} low cutoff (Hz)`} value={drafts[`low${f.n}`] ?? ""} onChange={(e) => setDrafts((d) => ({ ...d, [`low${f.n}`]: e.target.value }))} onBlur={(e) => commitNumber(f.n, "cutoff_low", e.target.value)} style={inputStyle} />
              </label>
            )}
            {f.kind !== "highpass" && (
              <label style={rowStyle}>
                High (Hz)
                <input aria-label={`Filter ${f.n} high cutoff (Hz)`} value={drafts[`high${f.n}`] ?? ""} onChange={(e) => setDrafts((d) => ({ ...d, [`high${f.n}`]: e.target.value }))} onBlur={(e) => commitNumber(f.n, "cutoff_high", e.target.value)} style={inputStyle} />
              </label>
            )}
            <label style={rowStyle}>
              Order
              <input aria-label={`Filter ${f.n} order`} value={drafts[`order${f.n}`] ?? ""} onChange={(e) => setDrafts((d) => ({ ...d, [`order${f.n}`]: e.target.value }))} onBlur={(e) => { const v = Number(e.target.value); if (Number.isInteger(v) && v >= 1 && v <= 10) patchFilter(f.n, { order: v }); }} style={inputStyle} />
            </label>
          </div>
        </GroupBox>
      ))}
      {error && <div role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)" }}>{error}</div>}
    </div>
  );
}
