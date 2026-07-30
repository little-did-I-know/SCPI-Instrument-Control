import { useState } from "react";
import { ApiError, api } from "../../api/client";
import type { TriggerPatch } from "../../api/types";
import { ComboBox } from "../../ds/ComboBox";
import { GroupBox } from "../../ds/GroupBox";
import { SpinBox } from "../../ds/SpinBox";
import { useSession } from "../../store/session";

const MODES = ["AUTO", "NORM", "SINGLE", "STOP"];
const SLOPES = ["POS", "NEG"];

function withNull(options: string[], value: string | null) {
  return value == null ? ["", ...options] : options;
}

export function TriggerPanel() {
  const session = useSession((s) => s.session);
  const trigger = useSession((s) => s.scope?.trigger);
  const numChannels = session?.num_channels ?? 0;
  const [error, setError] = useState<string | null>(null);

  async function send(patch: TriggerPatch) {
    if (!session) return;
    setError(null);
    try {
      await api.patchTrigger(session.id, patch);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  const sources = [...Array.from({ length: numChannels }, (_, i) => `C${i + 1}`), "EX", "LINE"];

  return (
    <GroupBox title="Trigger">
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
          Mode
          <ComboBox
            aria-label="Trigger mode"
            options={MODES}
            value={trigger?.mode ?? ""}
            onChange={(value) => send({ mode: value })}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
          Source
          <ComboBox
            aria-label="Trigger source"
            options={withNull(sources, trigger?.source ?? null)}
            value={trigger?.source ?? ""}
            onChange={(value) => send({ source: value })}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
          Slope
          <ComboBox
            aria-label="Trigger slope"
            options={withNull(SLOPES, trigger?.slope ?? null)}
            value={trigger?.slope ?? ""}
            onChange={(value) => send({ slope: value })}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}>
          Level
          <SpinBox
            aria-label="Trigger level"
            value={trigger?.level ?? 0}
            suffix=" V"
            onChange={(value) => send({ level: value })}
          />
        </div>
      </div>
      {error && (
        <div role="alert" style={{ padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {error}
        </div>
      )}
    </GroupBox>
  );
}
