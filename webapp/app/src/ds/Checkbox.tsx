import React from "react";

export type CheckboxProps = {
  label?: React.ReactNode;
  checked?: boolean;
  defaultChecked?: boolean;
  disabled?: boolean;
  bold?: boolean;
  onChange?: (value: boolean) => void;
  style?: React.CSSProperties;
} & Omit<React.LabelHTMLAttributes<HTMLLabelElement>, "onChange" | "style">;

/**
 * Checkbox — QCheckBox. Square box with a check, label to the right.
 * Used for Enable channel, Bandwidth Limit, Grid, Timestamp, Statistics…
 */
export function Checkbox({
  label,
  checked,
  defaultChecked = false,
  disabled = false,
  bold = false,
  onChange,
  style,
  ...rest
}: CheckboxProps) {
  const isControlled = checked !== undefined;
  const [internal, setInternal] = React.useState(defaultChecked);
  const value = isControlled ? checked : internal;

  const toggle = () => {
    if (disabled) return;
    if (!isControlled) setInternal(!value);
    onChange && onChange(!value);
  };

  return (
    <label
      onClick={toggle}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "8px",
        fontFamily: "var(--font-ui)",
        fontSize: "var(--text-sm)",
        fontWeight: bold ? "var(--weight-bold)" : "var(--weight-normal)",
        color: "var(--text-primary)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        userSelect: "none",
        ...style,
      }}
      {...rest}
    >
      <span
        style={{
          width: "17px",
          height: "17px",
          flexShrink: 0,
          borderRadius: "5px",
          border: `1px solid ${value ? "var(--success)" : "var(--lc-border-strong)"}`,
          background: value ? "var(--success)" : "var(--lc-control)",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "background-color 90ms ease, border-color 90ms ease",
        }}
      >
        {value && (
          <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
            <path d="M2.5 6.2L4.8 8.5L9.5 3.5" stroke="#fff" strokeWidth="1.8"
              strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </span>
      {label}
    </label>
  );
}
