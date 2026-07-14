import React from "react";

export type ToolbarProps = {
  children?: React.ReactNode;
  right?: React.ReactNode;
  style?: React.CSSProperties;
} & Omit<React.HTMLAttributes<HTMLDivElement>, "style">;

/**
 * Toolbar — the main window's top action bar (below the menu). A light strip
 * with a bottom border that holds action buttons on the left and, optionally,
 * status content pushed to the right. Compose Button (variant="ghost" for the
 * plain text actions) and StatusIndicator inside it.
 */
export function Toolbar({ children, right, style, ...rest }: ToolbarProps) {
  return (
    <div
      role="toolbar"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        minHeight: "var(--toolbar-height)",
        padding: "6px 10px",
        background: "var(--app-bg)",
        borderBottom: "1px solid var(--border)",
        fontFamily: "var(--font-ui)",
        ...style,
      }}
      {...rest}
    >
      {children}
      {right != null && (
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "10px" }}>
          {right}
        </div>
      )}
    </div>
  );
}

/** Thin vertical rule to group toolbar actions, mirroring the app's separators. */
export function ToolbarSeparator() {
  return (
    <span
      aria-hidden
      style={{
        width: "1px",
        alignSelf: "stretch",
        margin: "6px 4px",
        background: "var(--divider)",
      }}
    />
  );
}
