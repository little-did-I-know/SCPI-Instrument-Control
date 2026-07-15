import type { LogData, MeasurementValue } from "../../api/types";

export type TrendColumn = { channel: number; mtype: string };

const MAX_CLIENT_ROWS = 86400; // mirror the server ring buffer

let columns: TrendColumn[] = [];
let rows: (number | null)[][] = [];
const listeners = new Set<() => void>();

function notify(): void {
  listeners.forEach((listener) => listener());
}

export function seedTrend(data: LogData): void {
  columns = data.columns;
  rows = data.rows.slice(-MAX_CLIENT_ROWS);
  notify();
}

export function appendTrend(timestamp: number, values: MeasurementValue[]): void {
  if (columns.length === 0) return; // not seeded yet — the next seed backfills from the server
  const last = rows[rows.length - 1];
  if (last && (last[0] as number) >= timestamp) return; // duplicate or out-of-order sample
  const row: (number | null)[] = [timestamp, ...columns.map((c) => values.find((v) => v.channel === c.channel && v.mtype === c.mtype)?.value ?? null)];
  rows.push(row);
  if (rows.length > MAX_CLIENT_ROWS) rows = rows.slice(-MAX_CLIENT_ROWS);
  notify();
}

export function getTrend(): { columns: TrendColumn[]; rows: (number | null)[][] } {
  return { columns, rows };
}

export function clearTrend(): void {
  columns = [];
  rows = [];
  notify();
}

export function subscribeTrend(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
