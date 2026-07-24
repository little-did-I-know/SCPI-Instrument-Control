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
