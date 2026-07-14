import React from "react";

export type ReadingProps = {
  label?: React.ReactNode;
  value?: React.ReactNode;
  unit?: string;
  mode?: string;
  modeColor?: string;
  size?: "sm" | "lg";
  style?: React.CSSProperties;
} & Omit<React.HTMLAttributes<HTMLDivElement>, "style">;

/**
 * Reading — a live instrument readout. Monospace value in scope green
 * (#00ff00), as used for Measured V / I / W and the big front-panel numbers.
 * Optional CV/CC-style `mode` badge (green for CV, orange for CC).
 *
 *  - size "sm" : inline panel readout (PSU measured values)
 *  - size "lg" : front-panel hero number (e.g. "30.00 V")
 */
export function Reading({
  label,
  value,
  unit = "",
  mode,
  modeColor,
  size = "sm",
  style,
  ...rest
}: ReadingProps) {
  const big = size === "lg";
  return (
    <div
      style={{
        display: big ? "flex" : "inline-flex",
        flexDirection: big ? "column" : "row",
        alignItems: big ? "flex-start" : "baseline",
        gap: big ? "2px" : "8px",
        fontFamily: "var(--font-ui)",
        ...style,
      }}
      {...rest}
    >
      {label != null && (
        <span
          style={{
            fontSize: big ? "var(--text-xs)" : "var(--text-sm)",
            color: "var(--scope-text-muted)",
            textTransform: big ? "uppercase" : "none",
            letterSpacing: big ? "var(--tracking-label)" : 0,
          }}
        >
          {label}
        </span>
      )}
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: big ? "var(--text-2xl)" : "var(--text-base)",
          fontWeight: "var(--weight-bold)",
          color: "var(--readout)",
          lineHeight: 1,
          letterSpacing: "var(--tracking-mono)",
        }}
      >
        {value}
        {unit ? <span style={{ fontSize: "0.6em", marginLeft: "4px", opacity: 0.85 }}>{unit}</span> : null}
      </span>
      {mode != null && (
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "var(--text-xs)",
            fontWeight: "var(--weight-bold)",
            color: modeColor || (mode === "CC" ? "var(--warning)" : "var(--readout)"),
            border: `1px solid ${modeColor || (mode === "CC" ? "var(--warning)" : "var(--readout)")}`,
            borderRadius: "var(--radius-sm)",
            padding: "1px 5px",
          }}
        >
          {mode}
        </span>
      )}
    </div>
  );
}
