import { useState } from "react";
import { ApiError, api } from "../../api/client";
import { Button } from "../../ds/Button";
import type { SessionInfo } from "../../api/types";

export type OwnerBadgeProps = {
  session: SessionInfo;
  identity: string;
  onClaimed: () => void;
};

/**
 * Surfaces session ownership for a non-owner. The server enforces write
 * ownership (owner-only writes, everyone else gets 409) — this is the one
 * place that tells a non-owner *why* their writes would fail and offers a
 * path to take over. Deliberately renders nothing for the owner and for an
 * unowned session (`owner === ""`): reads (state, stream, captures, exports)
 * keep working for everyone regardless, so there is nothing to warn about
 * and no reason to add chrome the owner has to look past.
 */
export function OwnerBadge({ session, identity, onClaimed }: OwnerBadgeProps) {
  const [error, setError] = useState("");
  const [claiming, setClaiming] = useState(false);

  if (!session.owner || session.owner === identity) return null;

  const claim = async () => {
    setClaiming(true);
    setError("");
    try {
      await api.claimSession(session.id);
      onClaimed();
    } catch (caught) {
      // The server's 409 detail explains *why* the claim failed (owner still
      // active, or owner watching the stream) — that text is the only way the
      // user learns the owner is still there, so it must reach the screen.
      setError(caught instanceof ApiError ? caught.detail || caught.message : caught instanceof Error ? caught.message : "Claim failed.");
    } finally {
      setClaiming(false);
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "5px",
          fontSize: "var(--text-2xs)",
          color: "var(--warning)",
          border: "1px solid var(--lc-border)",
          borderRadius: "var(--radius-pill)",
          padding: "1px 9px",
        }}
      >
        <strong>Read-only</strong> — owned by {session.owner}
      </span>
      <Button type="button" size="sm" disabled={claiming} onClick={() => void claim()}>
        {claiming ? "Claiming…" : "Claim"}
      </Button>
      {error ? (
        <span role="alert" style={{ fontSize: "var(--text-xs)", color: "var(--danger)" }}>
          {error}
        </span>
      ) : null}
    </div>
  );
}
