import React from "react";

export type DataTableColumn = string | { label: string; width?: string | number; align?: React.CSSProperties["textAlign"]; mono?: boolean };
export type DataTableCell = React.ReactNode;

export type DataTableProps = {
  columns?: DataTableColumn[];
  rows?: DataTableCell[][];
  dark?: boolean;
  style?: React.CSSProperties;
} & Omit<React.TableHTMLAttributes<HTMLTableElement>, "style">;

/**
 * DataTable — QTableWidget. Column-headed table with alternating row colours.
 * Two treatments:
 *   light (default) — measurement panel (alt rows, native header)
 *   dark            — DAQ data view (#2d2d2d body, #353535 alt, #404040 header)
 *
 * `columns` are strings or {label, width, align}. `rows` are arrays of cells;
 * a cell may be a string/number or a React node (e.g. a channel-coloured value).
 */
export function DataTable({
  columns = [],
  rows = [],
  dark = false,
  style,
  ...rest
}: DataTableProps) {
  const cols = columns.map((c) => (typeof c === "string" ? { label: c } : c));
  const pal = dark
    ? {
        body: "var(--scope-surface)", alt: "var(--scope-row-alt)",
        header: "var(--scope-header)", grid: "var(--scope-border-3)",
        text: "#ffffff", headerText: "#ffffff",
      }
    : {
        body: "var(--surface)", alt: "var(--surface-alt)",
        header: "var(--surface-subtle)", grid: "var(--divider)",
        text: "var(--text-primary)", headerText: "var(--text-secondary)",
      };

  return (
    <table
      style={{
        width: "100%",
        borderCollapse: "collapse",
        fontFamily: "var(--font-ui)",
        fontSize: "var(--text-sm)",
        color: pal.text,
        background: pal.body,
        border: `1px solid ${pal.grid}`,
        ...style,
      }}
      {...rest}
    >
      <thead>
        <tr>
          {cols.map((c, i) => (
            <th
              key={i}
              style={{
                textAlign: c.align || "left",
                fontWeight: "var(--weight-bold)",
                color: pal.headerText,
                background: pal.header,
                padding: "7px 10px",
                borderBottom: `1px solid ${pal.grid}`,
                width: c.width || "auto",
                whiteSpace: "nowrap",
              }}
            >
              {c.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, ri) => (
          <tr key={ri} style={{ background: ri % 2 ? pal.alt : pal.body }}>
            {r.map((cell, ci) => (
              <td
                key={ci}
                style={{
                  padding: "6px 10px",
                  textAlign: cols[ci]?.align || "left",
                  borderBottom: `1px solid ${pal.grid}`,
                  fontFamily: cols[ci]?.mono ? "var(--font-mono)" : "inherit",
                  whiteSpace: "nowrap",
                }}
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
