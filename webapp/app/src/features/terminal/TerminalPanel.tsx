import { useState } from "react";
import { ApiError, api } from "../../api/client";
import { Terminal, type TerminalLine } from "../../ds/Terminal";
import { useSession } from "../../store/session";

export function TerminalPanel() {
  const session = useSession((s) => s.session);
  const [lines, setLines] = useState<TerminalLine[]>([]);

  async function onSend(command: string) {
    setLines((prev) => [...prev, { text: "> " + command, kind: "command" }]);
    if (!session) return;
    try {
      const result = await api.command(session.id, command);
      setLines((prev) => [
        ...prev,
        { text: result.response ?? "(no response)", kind: result.response ? "response" : "muted" },
      ]);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : String(err);
      setLines((prev) => [...prev, { text: detail, kind: "error" }]);
    }
  }

  return (
    <Terminal
      lines={lines}
      onSend={onSend}
      placeholder="Enter SCPI command here (e.g., *IDN?)"
      style={{ height: "100%" }}
    />
  );
}
