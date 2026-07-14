import React from "react";

export type SpinBoxProps = {
  value?: number;
  defaultValue?: number;
  min?: number;
  max?: number;
  step?: number;
  decimals?: number;
  suffix?: string;
  disabled?: boolean;
  onChange?: (value: number) => void;
  width?: string | number;
  style?: React.CSSProperties;
  /** Forwarded to the inner <input>, not the wrapper — see the destructure below. */
  name?: string;
} & Omit<React.HTMLAttributes<HTMLDivElement>, "onChange" | "style">;

/**
 * SpinBox — QDoubleSpinBox. Numeric field with a unit suffix and stacked
 * up/down steppers. Used for V/div, Offset, Trigger Level, Holdoff, Voltage &
 * Current setpoints. Suffix examples: " V", " A", " s".
 */
export function SpinBox({
  value,
  defaultValue = 0,
  min = -Infinity,
  max = Infinity,
  step = 0.1,
  decimals = 3,
  suffix = "",
  disabled = false,
  onChange,
  width,
  style,
  // ARIA/identity props belong on the real editable control, not the layout wrapper.
  // Spreading them onto the wrapper would leave the <input> with no accessible name,
  // so getByLabelText / screen readers would land on a non-editable <div>.
  "aria-label": ariaLabel,
  "aria-labelledby": ariaLabelledBy,
  "aria-describedby": ariaDescribedBy,
  id,
  name,
  ...rest
}: SpinBoxProps) {
  const isControlled = value !== undefined;
  const [internal, setInternal] = React.useState(defaultValue);
  const current = isControlled ? (value as number) : internal;
  const [hover, setHover] = React.useState(false);
  const [foc, setFoc] = React.useState(false);

  const clamp = (v: number) => Math.min(max, Math.max(min, v));
  const commit = (v: number) => {
    const c = clamp(v);
    if (!isControlled) setInternal(c);
    onChange && onChange(c);
  };

  const fmt = (v: number) =>
    (typeof v === "number" && !Number.isNaN(v) ? v : 0).toFixed(decimals) + suffix;

  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState("");

  const Stepper = ({ dir }: { dir: 1 | -1 }) => (
    <button
      type="button"
      disabled={disabled}
      tabIndex={-1}
      onClick={() => commit(current + dir * step)}
      style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        border: "none",
        borderLeft: "1px solid var(--lc-border)",
        borderBottom: dir > 0 ? "1px solid var(--lc-border)" : "none",
        background: "var(--lc-panel-2)",
        color: "var(--lc-text-2)",
        cursor: disabled ? "not-allowed" : "pointer",
        fontSize: "8px",
        lineHeight: 1,
        padding: 0,
      }}
    >
      {dir > 0 ? "▲" : "▼"}
    </button>
  );

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex",
        alignItems: "stretch",
        height: "32px",
        width: width || "140px",
        background: "var(--lc-control)",
        border: `1px solid ${foc ? "var(--lc-accent)" : hover && !disabled ? "var(--lc-border-strong)" : "var(--lc-border-strong)"}`,
        borderRadius: "var(--lc-radius-sm)",
        boxShadow: foc ? "0 0 0 3px var(--lc-accent-soft)" : "none",
        overflow: "hidden",
        opacity: disabled ? 0.5 : 1,
        fontFamily: "var(--font-ui)",
        ...style,
      }}
      {...rest}
    >
      <input
        type="text"
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        aria-describedby={ariaDescribedBy}
        id={id}
        name={name}
        disabled={disabled}
        value={editing ? draft : fmt(current)}
        onFocus={() => { setEditing(true); setDraft(String(current)); setFoc(true); }}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => { setEditing(false); setFoc(false); const n = parseFloat(draft); if (!Number.isNaN(n)) commit(n); }}
        onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
        style={{
          flex: 1,
          minWidth: 0,
          border: "none",
          outline: "none",
          background: "transparent",
          padding: "0 8px",
          fontFamily: "var(--font-ui)",
          fontSize: "var(--text-sm)",
          color: "var(--lc-text)",
        }}
      />
      <div style={{ display: "flex", flexDirection: "column", width: "18px" }}>
        <Stepper dir={1} />
        <Stepper dir={-1} />
      </div>
    </div>
  );
}
