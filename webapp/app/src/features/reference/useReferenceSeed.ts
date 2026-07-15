import { useEffect } from "react";
import { api } from "../../api/client";
import { setFrame } from "../waveform/frames";
import { useSession } from "../../store/session";

/** Seed the reference overlay from the server on session mount, so a ghost
 *  activated by another tab shows without opening the Reference panel. */
export function useReferenceSeed(sessionId: string | null): void {
  useEffect(() => {
    if (!sessionId) return;
    let stale = false;
    const before = useSession.getState().activeReference;
    api
      .getReference(sessionId)
      .then((overlay) => {
        // Snapshot guard: a live `reference` broadcast that landed while this
        // GET was in flight is fresher — never clobber it with mount data.
        if (stale || useSession.getState().activeReference !== before) return;
        setFrame("REF", { t0: overlay.t0, dt: overlay.dt, points: overlay.points });
        useSession.getState().applyReference(overlay.name ? { name: overlay.name, channel: overlay.channel } : null);
      })
      .catch(() => {});
    return () => {
      stale = true;
    };
  }, [sessionId]);
}
