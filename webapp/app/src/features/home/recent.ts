export type RecentEntry = {
  address: string | null;
  label: string;
  kind: string;
  model: string;
  mock: boolean;
};

export const RECENT_KEY = "scpi.recent";
const CAP = 5;

export function getRecent(): RecentEntry[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as RecentEntry[]) : [];
  } catch {
    return [];
  }
}

function sameTarget(a: RecentEntry, b: RecentEntry): boolean {
  return a.mock ? b.mock : !b.mock && a.address === b.address;
}

export function pushRecent(entry: RecentEntry): void {
  const next = [entry, ...getRecent().filter((e) => !sameTarget(e, entry))].slice(0, CAP);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    // storage full/unavailable — recent is a convenience, ignore
  }
}
