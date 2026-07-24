import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import { clearToken, getToken, setToken } from "../../api/token";
import { Button } from "../../ds/Button";
import { GroupBox } from "../../ds/GroupBox";

type Status = "checking" | "needs-token" | "ready";

const UNAUTHORIZED = "That token was not accepted.";
const UNREACHABLE = "Could not reach the server. Check your connection and try again.";

/**
 * Gates the app behind a verified bearer token. Every request already
 * carries whatever token is in storage; this is the one place that finds
 * out whether that token actually works, and is therefore also the one
 * place that can tell the user how to get a good one.
 *
 * A 401 means the token itself is bad, so it's cleared — a stale credential
 * shouldn't linger and keep failing silently. Any other failure (the
 * gateway restarting, a dropped connection) says nothing about the token,
 * so it's left in storage and the user can just retry.
 */
export function TokenGate({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>("checking");
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [hasStoredToken, setHasStoredToken] = useState(false);

  const check = useCallback(async () => {
    if (!getToken()) {
      setHasStoredToken(false);
      setError("");
      setStatus("needs-token");
      return;
    }
    try {
      await api.whoami();
      setError("");
      setStatus("ready");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken();
        setHasStoredToken(false);
        setError(UNAUTHORIZED);
      } else {
        setHasStoredToken(true);
        setError(UNREACHABLE);
      }
      setStatus("needs-token");
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  if (status === "ready") return <>{children}</>;
  // aria-live so a screen-reader user hears the wait; without it the first
  // screen of the app is silent until it resolves.
  if (status === "checking")
    return (
      <p role="status" aria-live="polite">
        Connecting…
      </p>
    );

  return (
    <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-4)" }}>
      <div style={{ width: "min(360px, 100%)" }}>
        <GroupBox title="Sign in">
          <form
            style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}
            onSubmit={(event) => {
              event.preventDefault();
              const trimmed = value.trim();
              if (!trimmed) return;
              setToken(trimmed);
              setValue("");
              setStatus("checking");
              void check();
            }}
          >
            <label htmlFor="token" style={{ fontSize: "var(--text-sm)", color: "var(--lc-text)" }}>
              Access token
            </label>
            <input
              id="token"
              type="password"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              autoComplete="off"
              style={{ padding: "6px 8px", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", border: "1px solid var(--lc-border-strong)", borderRadius: "var(--lc-radius-sm)", background: "var(--lc-control)", color: "var(--lc-text)" }}
            />
            <div style={{ display: "flex", gap: "var(--space-1)" }}>
              <Button type="submit" variant="primary" disabled={!value.trim()} fullWidth>
                Connect
              </Button>
              {hasStoredToken && (
                <Button
                  type="button"
                  onClick={() => {
                    setStatus("checking");
                    void check();
                  }}
                >
                  Retry
                </Button>
              )}
            </div>
            {error ? (
              <p role="alert" style={{ margin: 0, padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", color: "var(--danger)", fontSize: "var(--text-sm)" }}>
                {error}
              </p>
            ) : null}
            <p style={{ margin: 0, fontSize: "var(--text-xs)", color: "var(--lc-muted)" }}>
              No token? Run <code>scpi-web token add &lt;name&gt;</code> on the gateway host to mint one.
            </p>
          </form>
        </GroupBox>
      </div>
    </div>
  );
}
