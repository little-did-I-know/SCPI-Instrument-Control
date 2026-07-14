import { Button } from "../../ds/Button";
import { getRecent, type RecentEntry } from "./recent";

type Props = { onReconnect: (entry: RecentEntry) => void };

export function RecentBar({ onReconnect }: Props) {
  const recents = getRecent();
  if (recents.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-1)" }}>
      {recents.map((entry) => (
        <Button key={entry.mock ? "mock" : entry.address ?? ""} size="sm" aria-label={`Reconnect ${entry.label}`} onClick={() => onReconnect(entry)}>
          ↻ {entry.label}
        </Button>
      ))}
    </div>
  );
}
