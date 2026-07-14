import React from "react";

/**
 * Terminal — the SCPI command console (TerminalWidget). Dark #1e1e1e panel,
 * Courier New, colour-coded lines. Optional input row with the signature
 * green-bordered field + Send / Clear buttons.
 *
 * `lines` is an array of { text, kind } where kind ∈
 *   command | response | ok | error | muted | plain
 */
const LINE_COLORS = {
  command: "var(--term-command)",
  response: "var(--term-response)",
  ok: "var(--term-ok)",
  error: "var(--term-error)",
  muted: "var(--term-muted)",
  plain: "var(--scope-text-body)",
};

export function Terminal({
  lines = [],
  showInput = true,
  placeholder = "Enter SCPI command here (e.g., *IDN?)",
  onSend,
  style,
  ...rest
}) {
  const [cmd, setCmd] = React.useState("");
  const [focus, setFocus] = React.useState(false);
  const send = () => {
    const v = cmd.trim();
    if (!v) return;
    onSend && onSend(v);
    setCmd("");
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        fontFamily: "var(--font-mono)",
        ...style,
      }}
      {...rest}
    >
      <div
        style={{
          background: "var(--scope-panel)",
          color: "var(--scope-text-body)",
          border: "1px solid var(--scope-border-soft)",
          borderRadius: "var(--radius-sm)",
          padding: "10px 12px",
          fontSize: "var(--text-sm)",
          lineHeight: 1.55,
          overflowY: "auto",
          flex: 1,
          minHeight: 0,
        }}
      >
        {lines.length === 0 && (
          <div style={{ color: "var(--term-ok)" }}>=== SCPI Terminal Ready ===</div>
        )}
        {lines.map((l, i) => (
          <div key={i} style={{ color: LINE_COLORS[l.kind] || LINE_COLORS.plain, whiteSpace: "pre-wrap" }}>
            {l.text}
          </div>
        ))}
      </div>

      {showInput && (
        <div style={{ display: "flex", gap: "8px" }}>
          <input
            value={cmd}
            placeholder={placeholder}
            onChange={(e) => setCmd(e.target.value)}
            onFocus={() => setFocus(true)}
            onBlur={() => setFocus(false)}
            onKeyDown={(e) => { if (e.key === "Enter") send(); }}
            style={{
              flex: 1,
              minWidth: 0,
              fontFamily: "var(--font-mono)",
              fontSize: "var(--text-sm)",
              color: "var(--text-primary)",
              background: "var(--surface)",
              padding: "6px 8px",
              border: `2px solid ${focus ? "var(--success-hover)" : "var(--success)"}`,
              borderRadius: "var(--radius-sm)",
              outline: "none",
            }}
          />
          <button
            type="button"
            onClick={send}
            style={{
              background: "var(--success)", color: "#fff", fontWeight: "var(--weight-bold)",
              fontFamily: "var(--font-ui)", border: "none", borderRadius: "var(--radius-sm)",
              padding: "6px 20px", cursor: "pointer",
            }}
          >
            Send
          </button>
        </div>
      )}
    </div>
  );
}
