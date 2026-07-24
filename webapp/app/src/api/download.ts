import { ApiError } from "./client";
import { getToken } from "./token";

/** Fetch a file with the bearer token, then hand it to the browser as a download.
 *
 * A plain <a href download> cannot carry an Authorization header, and the server
 * rejects query-parameter tokens on /api/* — so authenticated downloads have to
 * go through fetch and a blob URL.
 */
export async function downloadAuthenticated(url: string, filename: string): Promise<void> {
  const token = getToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(url, { headers });
  if (!response.ok) {
    let error = "Error";
    let detail = "download failed";
    try {
      const body = await response.json();
      error = body.error ?? error;
      detail = body.detail ?? detail;
    } catch {
      // non-JSON error body: keep defaults
    }
    throw new ApiError(response.status, error, detail);
  }
  const objectUrl = URL.createObjectURL(await response.blob());
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
