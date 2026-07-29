export type Identity = { name: string; devices: number; last_used: string | null };
export type Invitation = { id: string; name: string; code: string; expires: number; link?: string };
export type RevocationResult = { devices: number; streams: number; sessions: number };

/** The gateway's own session_out() payload, plus idle_seconds (see admin/api.py::list_sessions). */
export type Session = {
  id: string;
  label: string;
  kind: string;
  mock: boolean;
  address: string | null;
  state: string;
  idn: string;
  model: string;
  dialect: string;
  num_channels: number;
  viewers: number;
  owner: string;
  idle_seconds: number;
};

/**
 * Admin API client. Deliberately does NOT attach a bearer token: this app is
 * served only on a loopback-bound listener, and the boundary is that bind.
 * Sending a credential would imply a permission model that does not exist.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = "request failed";
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      // non-JSON error body: keep the default
    }
    throw new Error(detail);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const adminApi = {
  identities: () => request<Identity[]>("/api/identities"),
  invitations: () => request<Invitation[]>("/api/invitations"),
  createInvitation: (name: string) => request<Invitation>("/api/invitations", json("POST", { name })),
  cancelInvitation: (id: string) => request<void>(`/api/invitations/${id}`, { method: "DELETE" }),
  // 200 with the torn-down counts, not 204 -- so the panel can report what
  // revoking actually did instead of a generic "done".
  revokeIdentity: (name: string) => request<RevocationResult>(`/api/identities/${encodeURIComponent(name)}`, { method: "DELETE" }),
  sessions: () => request<Session[]>("/api/sessions"),
  releaseSession: (id: string) => request<void>(`/api/sessions/${id}/release`, { method: "POST" }),
  closeSession: (id: string) => request<void>(`/api/sessions/${id}`, { method: "DELETE" }),
};
