const STORAGE_KEY = "scpi.token";

export function getToken(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setToken(value: string): void {
  localStorage.setItem(STORAGE_KEY, value);
}

export function clearToken(): void {
  localStorage.removeItem(STORAGE_KEY);
}

/** Move a ?token= from the initial SPA load into storage, then strip it from the URL. */
export function captureTokenFromUrl(): void {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get("token");
  if (!fromUrl) return;
  setToken(fromUrl);
  params.delete("token");
  const query = params.toString();
  window.history.replaceState({}, "", window.location.pathname + (query ? `?${query}` : ""));
}

/**
 * Exchange an `?invite=` from the initial SPA load for a real token.
 *
 * The parameter is stripped BEFORE the request goes out, not after it
 * succeeds: if the gateway is slow or unreachable, a credential left sitting
 * in the address bar goes into history and leaks through the `Referer` of the
 * next link the user clicks. Stripping first costs nothing — the value is
 * already in hand.
 *
 * Every failure is silent by design. A bad or expired invite should land the
 * user on the ordinary sign-in screen, which already knows how to ask for a
 * code; a second error message here would just be noise about a link they
 * were probably sent by someone else.
 */
export async function redeemInviteFromUrl(): Promise<void> {
  const params = new URLSearchParams(window.location.search);
  const invite = params.get("invite");
  if (!invite) return;
  params.delete("invite");
  const query = params.toString();
  window.history.replaceState({}, "", window.location.pathname + (query ? `?${query}` : ""));
  try {
    const response = await fetch("/api/join", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ invite }),
    });
    if (!response.ok) return;
    const body = (await response.json()) as { token?: string };
    if (body.token) setToken(body.token);
  } catch {
    // Unreachable gateway: leave the user unauthenticated and let the
    // sign-in screen report the connection problem in its own words.
  }
}
