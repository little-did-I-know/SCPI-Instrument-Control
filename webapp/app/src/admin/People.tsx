import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "../ds/Button";
import { DataTable } from "../ds/DataTable";
import { GroupBox } from "../ds/GroupBox";
import { Countdown } from "./Countdown";
import { adminApi, type Identity, type Invitation } from "./api";

function formatDevices(count: number): string {
  return `${count} device${count === 1 ? "" : "s"}`;
}

/** Coarse "N units ago" for a last-used timestamp. `null` means never used. */
function formatLastUsed(lastUsed: string | null): string {
  if (!lastUsed) return "never";
  const then = Date.parse(lastUsed);
  if (Number.isNaN(then)) return "unknown";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

/** "417902" -> "417 902". Splits evenly; codes are an even length by construction. */
function groupCode(code: string): string {
  const mid = Math.ceil(code.length / 2);
  return `${code.slice(0, mid)} ${code.slice(mid)}`;
}

async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Clipboard access can be denied or unavailable (permissions, insecure
    // context). There's nothing more to do here -- the value is already on
    // screen as plain text for the admin to select by hand.
  }
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong.";
}

export function People() {
  const [identities, setIdentities] = useState<Identity[] | null>(null);
  const [invitations, setInvitations] = useState<Invitation[] | null>(null);
  const [error, setError] = useState("");

  const [revokeTarget, setRevokeTarget] = useState<Identity | null>(null);
  const [revoking, setRevoking] = useState(false);

  const [inviteName, setInviteName] = useState("");
  const [inviting, setInviting] = useState(false);
  const [created, setCreated] = useState<Invitation | null>(null);

  const dialogRef = useRef<HTMLDivElement>(null);

  const loadIdentities = useCallback(async () => {
    setIdentities(await adminApi.identities());
  }, []);
  const loadInvitations = useCallback(async () => {
    setInvitations(await adminApi.invitations());
  }, []);

  useEffect(() => {
    void loadIdentities();
    void loadInvitations();
  }, [loadIdentities, loadInvitations]);

  // Move focus into the confirmation so keyboard and screen-reader users land
  // on it rather than having to hunt for a dialog that appeared elsewhere.
  useEffect(() => {
    if (revokeTarget) dialogRef.current?.focus();
  }, [revokeTarget]);

  const confirmRevoke = async () => {
    if (!revokeTarget) return;
    setError("");
    setRevoking(true);
    try {
      await adminApi.revokeIdentity(revokeTarget.name);
      setRevokeTarget(null);
      await loadIdentities();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRevoking(false);
    }
  };

  const submitInvite = async (event: FormEvent) => {
    event.preventDefault();
    const name = inviteName.trim();
    if (!name) return;
    setError("");
    setInviting(true);
    try {
      const invite = await adminApi.createInvitation(name);
      setCreated(invite);
      setInviteName("");
      await loadInvitations();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setInviting(false);
    }
  };

  const cancelInvite = async (id: string) => {
    setError("");
    try {
      await adminApi.cancelInvitation(id);
      setCreated((current) => (current?.id === id ? null : current));
      await loadInvitations();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      {error ? (
        <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)" }}>
          {error}
        </p>
      ) : null}

      <GroupBox title="Who has access">
        {identities === null ? (
          <p>Loading…</p>
        ) : identities.length === 0 ? (
          <p>No one has access yet. Invite someone below to get started.</p>
        ) : (
          <DataTable
            columns={["Name", "Devices", "Last used", ""]}
            rows={identities.map((identity) => [
              identity.name,
              formatDevices(identity.devices),
              formatLastUsed(identity.last_used),
              <Button
                size="sm"
                variant="danger"
                disabled={revokeTarget !== null}
                onClick={() => setRevokeTarget(identity)}
              >
                Revoke
              </Button>,
            ])}
          />
        )}
      </GroupBox>

      <GroupBox title="Invitations">
        <form
          onSubmit={(event) => void submitInvite(event)}
          style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-end", marginBottom: "var(--space-3)" }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label htmlFor="invite-name" style={{ fontSize: "var(--text-sm)", color: "var(--lc-text)" }}>
              Name
            </label>
            <input
              id="invite-name"
              value={inviteName}
              onChange={(event) => setInviteName(event.target.value)}
              style={{
                padding: "6px 8px",
                fontSize: "var(--text-sm)",
                border: "1px solid var(--lc-border-strong)",
                borderRadius: "var(--lc-radius-sm)",
                background: "var(--lc-control)",
                color: "var(--lc-text)",
              }}
            />
          </div>
          <Button type="submit" variant="primary" disabled={inviting || !inviteName.trim()}>
            Invite
          </Button>
        </form>

        {created ? (
          <div style={{ marginBottom: "var(--space-3)", display: "flex", flexDirection: "column", gap: "6px" }}>
            <p>
              Invitation created for <strong>{created.name}</strong> — expires in <Countdown expires={created.expires} />.
            </p>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <code style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-lg)", letterSpacing: "0.1em" }}>
                {groupCode(created.code)}
              </code>
              <Button size="sm" onClick={() => void copyToClipboard(created.code)}>
                Copy code
              </Button>
            </div>
            {created.link ? (
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <code style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", wordBreak: "break-all" }}>
                  {created.link}
                </code>
                <Button size="sm" onClick={() => void copyToClipboard(created.link as string)}>
                  Copy link
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}

        {invitations && invitations.length > 0 ? (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: "6px" }}>
            {invitations.map((invite) => (
              <li
                key={invite.id}
                style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "var(--text-sm)" }}
              >
                <span>{invite.name}</span>
                <span>
                  <Countdown expires={invite.expires} />
                </span>
                <Button size="sm" onClick={() => void cancelInvite(invite.id)}>
                  Cancel invitation
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
      </GroupBox>

      {revokeTarget ? (
        <div
          role="alertdialog"
          aria-label={`Revoke ${revokeTarget.name}?`}
          aria-modal="true"
          tabIndex={-1}
          ref={dialogRef}
          style={{
            border: "1px solid var(--lc-border-strong)",
            borderRadius: "var(--lc-radius)",
            background: "var(--lc-panel)",
            boxShadow: "var(--lc-elev-1)",
            padding: "var(--space-3)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-2)",
            maxWidth: "360px",
          }}
        >
          <p>
            Revoke {revokeTarget.name}? This signs out all {revokeTarget.devices} of their devices.
          </p>
          <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
            <Button disabled={revoking} onClick={() => setRevokeTarget(null)}>
              Cancel
            </Button>
            <Button variant="danger" disabled={revoking} onClick={() => void confirmRevoke()}>
              Revoke
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
