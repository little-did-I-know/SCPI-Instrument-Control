import React from "react";

/**
 * Button — the app's push button (QPushButton).
 *
 * Variants map to the real setStyleSheet blocks in the PyQt6 source:
 *  - default  : native light Qt button (Auto Scale, Add, Update Now…)
 *  - primary  : Connect / Send — success green (#4CAF50)
 *  - danger   : Disconnect / Clear — red (#f44336)
 *  - critical : "All Outputs OFF (Safety)" — crimson, larger radius/padding
 *  - ghost    : flat toolbar text actions (Run, Stop, Single, Capture…)
 */
export function Button({
  children,
  variant = "default",
  size = "md",
  icon = null,
  disabled = false,
  fullWidth = false,
  onClick,
  type = "button",
  style,
  ...rest
}) {
  const sizes = {
    sm: { fontSize: "var(--text-xs)", padding: "4px 12px", height: "var(--control-height-sm)" },
    md: { fontSize: "var(--text-sm)", padding: "7px 20px", height: "32px" },
  };

  const base = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "6px",
    fontFamily: "var(--font-ui)",
    fontWeight: "var(--weight-medium)",
    lineHeight: 1,
    border: "1px solid transparent",
    borderRadius: "var(--lc-radius-sm)",
    cursor: disabled ? "not-allowed" : "pointer",
    userSelect: "none",
    whiteSpace: "nowrap",
    transition: "background-color 90ms ease, border-color 90ms ease, filter 90ms ease",
    width: fullWidth ? "100%" : "auto",
    opacity: disabled ? 0.5 : 1,
    ...sizes[size],
  };

  const variants = {
    default: {
      background: "var(--lc-panel)",
      borderColor: "var(--lc-border-strong)",
      color: "var(--lc-text)",
    },
    primary: {
      background: "var(--success)",
      color: "#ffffff",
      fontWeight: "var(--weight-bold)",
      borderColor: "transparent",
    },
    danger: {
      background: "var(--danger)",
      color: "#ffffff",
      fontWeight: "var(--weight-bold)",
      borderColor: "transparent",
    },
    critical: {
      background: "var(--critical)",
      color: "#ffffff",
      fontWeight: "var(--weight-bold)",
      borderRadius: "var(--radius-md)",
      padding: "10px 20px",
      borderColor: "transparent",
    },
    ghost: {
      background: "transparent",
      color: "var(--text-primary)",
      borderColor: "transparent",
      padding: size === "sm" ? "4px 10px" : "6px 14px",
    },
  };

  const hoverBg = {
    default: "var(--lc-control-hover)",
    primary: "var(--success-hover)",
    danger: "var(--danger-hover)",
    critical: "var(--critical-hover)",
    ghost: "rgba(0,0,0,0.06)",
  };
  const pressBg = {
    default: "var(--lc-panel-2)",
    primary: "var(--success-pressed)",
    danger: "var(--danger-pressed)",
    critical: "var(--critical-hover)",
    ghost: "rgba(0,0,0,0.11)",
  };

  const [state, setState] = React.useState("rest");
  const dyn =
    !disabled && state === "hover" ? { background: hoverBg[variant] } :
    !disabled && state === "active" ? { background: pressBg[variant] } : {};

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setState("hover")}
      onMouseLeave={() => setState("rest")}
      onMouseDown={() => setState("active")}
      onMouseUp={() => setState("hover")}
      style={{ ...base, ...variants[variant], ...dyn, ...style }}
      {...rest}
    >
      {icon && <span style={{ display: "inline-flex", fontSize: "1.05em" }}>{icon}</span>}
      {children}
    </button>
  );
}
