import { useEffect, useState } from "react";

/** Time left until `expires` (epoch seconds), as m:ss. */
export function Countdown({ expires }: { expires: number }) {
  const [now, setNow] = useState(() => Date.now() / 1000);

  useEffect(() => {
    // One interval per mounted countdown, cleared on unmount. Pending
    // invitations come and go as they are created and cancelled, so a leaked
    // timer here accumulates for as long as the panel stays open.
    const timer = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(timer);
  }, []);

  const left = Math.max(0, Math.floor(expires - now));
  if (left === 0) return <span>expired</span>;
  const minutes = Math.floor(left / 60);
  const seconds = String(left % 60).padStart(2, "0");
  return <span>{`${minutes}:${seconds}`}</span>;
}
