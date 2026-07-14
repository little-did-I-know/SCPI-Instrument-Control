import React from "react";

/**
 * StatusIndicator — connection status dot + label, from the toolbar/status bar.
 * Colours match the README legend:
 *   connected  🟢 green   connecting 🟡 orange
 *   disconnected 🔴 red    error      🟠 dark orange
 */
const STATES = {
  connected: { color: "var(--success)", text: "Connected" },
  connecting: { color: "var(--warning)", text: "Connecting…" },
  disconnected: { color: "var(--danger)", text: "Disconnected" },
  error: { color: "var(--ch8)", text: "Error" },
};

export function StatusIndicator({
  state = "disconnected",
  label,
  pulse,
  dark = false,
  style,
  ...rest
}) {
  const s = STATES[state] || STATES.disconnected;
  const doPulse = pulse ?? state === "connecting";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "7px",
        fontFamily: "var(--font-ui)",
        fontSize: "var(--text-sm)",
        color: dark ? "var(--scope-text-body)" : "var(--text-secondary)",
        ...style,
      }}
      {...rest}
    >
      <span
        style={{
          width: "9px",
          height: "9px",
          borderRadius: "var(--radius-pill)",
          background: s.color,
          boxShadow: `0 0 0 3px color-mix(in srgb, ${s.color} 22%, transparent)`,
          animation: doPulse ? "scpi-pulse 1.1s ease-in-out infinite" : "none",
          flexShrink: 0,
        }}
      />
      <span>{label ?? s.text}</span>
      <style>{`@keyframes scpi-pulse{0%,100%{opacity:1}50%{opacity:.35}}`}</style>
    </span>
  );
}
