import React from "react";

export type TabItem = string | { label: string; value: string };

export type TabsProps = {
  tabs?: TabItem[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  children?: React.ReactNode;
  style?: React.CSSProperties;
} & Omit<React.HTMLAttributes<HTMLDivElement>, "onChange" | "style">;

/**
 * Tabs — QTabWidget tab bar. The control panel's primary navigation
 * (Channels / Trigger / Timebase / Measurements / …). Light native styling
 * with an underline on the active tab.
 */
export function Tabs({
  tabs = [],
  value,
  defaultValue,
  onChange,
  children,
  style,
  ...rest
}: TabsProps) {
  const norm = tabs.map((t) => (typeof t === "string" ? { label: t, value: t } : t));
  const isControlled = value !== undefined;
  const [internal, setInternal] = React.useState(
    defaultValue ?? (norm[0] && norm[0].value)
  );
  const active = isControlled ? value : internal;
  const [_hover, setHover] = React.useState<string | null>(null);

  const select = (v: string) => {
    if (!isControlled) setInternal(v);
    onChange && onChange(v);
  };

  return (
    <div style={{ fontFamily: "var(--font-ui)", ...style }} {...rest}>
      <div
        role="tablist"
        style={{
          display: "inline-flex",
          gap: "3px",
          padding: "4px",
          background: "var(--lc-panel-2)",
          border: "1px solid var(--lc-border)",
          borderRadius: "var(--lc-radius)",
        }}
      >
        {norm.map((t) => {
          const on = t.value === active;
          return (
            <button
              key={t.value}
              role="tab"
              aria-selected={on}
              onClick={() => select(t.value)}
              onMouseEnter={() => setHover(t.value)}
              onMouseLeave={() => setHover(null)}
              style={{
                border: "none",
                background: on ? "var(--lc-panel)" : "transparent",
                color: on ? "var(--lc-text)" : "var(--lc-text-2)",
                fontSize: "var(--text-sm)",
                fontWeight: on ? "var(--weight-medium)" : "500",
                padding: "7px 14px",
                cursor: "pointer",
                borderRadius: "var(--lc-radius-sm)",
                boxShadow: on ? "var(--lc-elev-1)" : "none",
                whiteSpace: "nowrap",
                transition: "background 90ms ease, color 90ms ease",
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      {children != null && <div style={{ paddingTop: "12px" }}>{children}</div>}
    </div>
  );
}
