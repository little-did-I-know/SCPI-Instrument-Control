import { useEffect } from "react";
import { GroupBox } from "../../ds/GroupBox";
import { useSession } from "../../store/session";
import { kindMeta } from "../home/kinds";
import { KIND_VIEWS } from "./kindViews";
import { TerminalDrawer } from "./TerminalDrawer";
import { useTerminalDrawer } from "./useTerminalDrawer";

/** The in-session frame. Looks up the connected instrument's kind in the
 *  registry and renders what it declared -- and nothing else knows about
 *  kinds. */
export function InstrumentShell() {
  const session = useSession((s) => s.session);
  const sessionId = session?.id ?? null;
  // A drawer left open against a previous instrument should not reopen against
  // the next one, whose kind and command set are different.
  useEffect(() => {
    useTerminalDrawer.getState().close();
  }, [sessionId]);
  if (session === null) return null;
  const view = KIND_VIEWS[session.kind];
  if (view === undefined) {
    return (
      <>
        <GroupBox title={kindMeta(session.kind).label}>
          <p style={{ margin: 0, color: "var(--lc-muted)" }}>A dedicated view for this instrument kind is coming soon.</p>
        </GroupBox>
        <TerminalDrawer />
      </>
    );
  }
  const Readout = view.readout;
  const Body = view.body;
  return (
    <>
      {Readout !== undefined && <Readout />}
      <Body />
      <TerminalDrawer />
    </>
  );
}
