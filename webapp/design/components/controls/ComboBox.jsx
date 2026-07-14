import React from "react";

/**
 * ComboBox — QComboBox dropdown. Native light Qt select with a chevron.
 * Used for Coupling (DC/AC/GND), Probe ratio, Trigger Mode/Source/Slope,
 * Channel pickers, Math operation, Window function…
 */
export function ComboBox({
  options = [],
  value,
  defaultValue,
  disabled = false,
  onChange,
  width,
  style,
  ...rest
}) {
  const norm = options.map((o) =>
    typeof o === "string" ? { label: o, value: o } : o
  );
  const isControlled = value !== undefined;
  const [internal, setInternal] = React.useState(
    defaultValue ?? (norm[0] && norm[0].value)
  );
  const current = isControlled ? value : internal;

  const [hover, setHover] = React.useState(false);
  const [foc, setFoc] = React.useState(false);

  const handle = (e) => {
    const v = e.target.value;
    if (!isControlled) setInternal(v);
    onChange && onChange(v);
  };

  return (
    <div
      style={{ position: "relative", display: "inline-block", width: width || "auto", ...style }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <select
        value={current}
        disabled={disabled}
        onChange={handle}
        style={{
          appearance: "none",
          WebkitAppearance: "none",
          MozAppearance: "none",
          width: "100%",
          height: "32px",
          padding: "0 28px 0 10px",
          fontFamily: "var(--font-ui)",
          fontSize: "var(--text-sm)",
          color: "var(--lc-text)",
          background: "var(--lc-control)",
          border: `1px solid ${foc ? "var(--lc-accent)" : hover && !disabled ? "var(--lc-border-strong)" : "var(--lc-border-strong)"}`,
          borderRadius: "var(--lc-radius-sm)",
          boxShadow: foc ? "0 0 0 3px var(--lc-accent-soft)" : "none",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.5 : 1,
          outline: "none",
        }}
        onFocus={() => setFoc(true)}
        onBlur={() => setFoc(false)}
        {...rest}
      >
        {norm.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <span
        aria-hidden
        style={{
          position: "absolute",
          right: "9px",
          top: "50%",
          transform: "translateY(-50%)",
          pointerEvents: "none",
          color: "var(--lc-text-2)",
          fontSize: "10px",
          lineHeight: 1,
        }}
      >
        ▾
      </span>
    </div>
  );
}
