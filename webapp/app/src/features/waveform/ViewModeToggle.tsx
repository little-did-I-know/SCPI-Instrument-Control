const MODES = ["Time", "Spectrum", "Trend"] as const;
export type ViewMode = (typeof MODES)[number];

export function ViewModeToggle({ value, onChange }: { value: ViewMode; onChange: (mode: ViewMode) => void }) {
  return (
    <div role="group" aria-label="Canvas view" style={{ display: "inline-flex", gap: 2 }}>
      {MODES.map((mode) => (
        <button
          key={mode}
          aria-pressed={value === mode}
          onClick={() => onChange(mode)}
          style={{
            padding: "4px 12px",
            fontSize: "var(--text-sm)",
            fontFamily: "var(--font-ui)",
            borderRadius: "var(--lc-radius-sm)",
            border: "1px solid var(--lc-border-strong)",
            background: value === mode ? "var(--lc-control)" : "transparent",
            color: value === mode ? "var(--lc-text)" : "var(--lc-muted)",
            cursor: "pointer",
          }}
        >
          {mode}
        </button>
      ))}
    </div>
  );
}
