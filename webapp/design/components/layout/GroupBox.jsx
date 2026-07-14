import React from "react";

/**
 * GroupBox — QGroupBox. A titled, bordered container. The title sits in a
 * notch on the top border. In the scope UI the title is colour-coded to the
 * channel it controls (gold / cyan / pink / green), so `titleColor` accepts
 * any CSS color or a channel token var.
 *
 * On the dark scope canvas set `dark` for the panel treatment.
 */
export function GroupBox({
  title,
  titleColor,
  dark = false,
  children,
  style,
  bodyStyle,
  ...rest
}) {
  const frame = dark ? "var(--scope-border-2)" : "var(--lc-border)";
  const bg = dark ? "var(--scope-panel)" : "var(--lc-panel)";
  const notchBg = dark ? "var(--scope-panel)" : "var(--lc-bg)";
  const defaultTitle = dark ? "var(--scope-text)" : "var(--lc-text-2)";

  return (
    <fieldset
      style={{
        position: "relative",
        margin: 0,
        padding: "14px 12px 12px",
        border: `1px solid ${frame}`,
        borderRadius: "var(--lc-radius)",
        background: bg,
        boxShadow: dark ? "none" : "var(--lc-elev-1)",
        minInlineSize: "auto",
        ...style,
      }}
      {...rest}
    >
      {title != null && (
        <legend
          style={{
            padding: "0 6px",
            marginLeft: "4px",
            fontFamily: "var(--font-ui)",
            fontSize: "var(--text-sm)",
            fontWeight: "var(--weight-bold)",
            color: titleColor || defaultTitle,
            background: notchBg,
          }}
        >
          {title}
        </legend>
      )}
      <div style={bodyStyle}>{children}</div>
    </fieldset>
  );
}
