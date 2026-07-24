import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TokenGate } from "./TokenGate";
import { clearToken, getToken, setToken } from "../../api/token";

describe("TokenGate", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("asks for a token when none is stored", () => {
    clearToken();
    render(<TokenGate><div>inside</div></TokenGate>);
    expect(screen.getByLabelText(/access token/i)).toBeInTheDocument();
    expect(screen.queryByText("inside")).not.toBeInTheDocument();
  });

  it("renders children once a token verifies", async () => {
    setToken("scpi_good");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ identity: "robin" }), { status: 200 })));
    render(<TokenGate><div>inside</div></TokenGate>);
    await waitFor(() => expect(screen.getByText("inside")).toBeInTheDocument());
  });

  it("re-prompts when the stored token is rejected", async () => {
    setToken("scpi_stale");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "Unauthorized", detail: "bad" }), { status: 401 })));
    render(<TokenGate><div>inside</div></TokenGate>);
    await waitFor(() => expect(screen.getByLabelText(/access token/i)).toBeInTheDocument());
  });

  it("clears the rejected token so a blank resubmit can't silently reuse it", async () => {
    setToken("scpi_stale");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "Unauthorized", detail: "bad" }), { status: 401 })));
    render(<TokenGate><div>inside</div></TokenGate>);
    await waitFor(() => expect(screen.getByLabelText(/access token/i)).toBeInTheDocument());
    expect(getToken()).toBeNull();
  });

  it("accepts a pasted token", async () => {
    clearToken();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ identity: "robin" }), { status: 200 })));
    render(<TokenGate><div>inside</div></TokenGate>);
    await userEvent.type(screen.getByLabelText(/access token/i), "scpi_pasted");
    await userEvent.click(screen.getByRole("button", { name: /connect/i }));
    await waitFor(() => expect(screen.getByText("inside")).toBeInTheDocument());
  });

  it("explains how to obtain a token", () => {
    clearToken();
    render(<TokenGate><div>inside</div></TokenGate>);
    expect(screen.getByText(/scpi-web token add/i)).toBeInTheDocument();
  });

  it("does not discard a stored token on a network error, and lets the user retry without retyping it", async () => {
    setToken("scpi_good");
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(new Response(JSON.stringify({ identity: "robin" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<TokenGate><div>inside</div></TokenGate>);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not reach|connection/i);
    // a network blip is not proof the token is bad: it must still be in storage
    expect(getToken()).toBe("scpi_good");
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByText("inside")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not discard a stored token on a non-401 server error", async () => {
    setToken("scpi_good");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "ServerError", detail: "restarting" }), { status: 500 })));
    render(<TokenGate><div>inside</div></TokenGate>);
    await screen.findByRole("alert");
    expect(getToken()).toBe("scpi_good");
  });
});
