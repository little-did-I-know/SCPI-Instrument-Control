import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TokenGate } from "./TokenGate";
import { clearToken, getToken, setToken } from "../../api/token";
import { useIdentity } from "../../store/identity";

describe("TokenGate", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    useIdentity.getState().clearIdentity();
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

  it("captures whoami's identity so the rest of the app can read it", async () => {
    setToken("scpi_good");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ identity: "robin" }), { status: 200 })));
    render(<TokenGate><div>inside</div></TokenGate>);
    await waitFor(() => expect(screen.getByText("inside")).toBeInTheDocument());
    expect(useIdentity.getState().identity).toBe("robin");
  });

  it("clears the identity when a stored token is rejected", async () => {
    setToken("scpi_stale");
    useIdentity.getState().setIdentity("stale-identity");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "Unauthorized", detail: "bad" }), { status: 401 })));
    render(<TokenGate><div>inside</div></TokenGate>);
    await waitFor(() => expect(screen.getByLabelText(/access token/i)).toBeInTheDocument());
    expect(useIdentity.getState().identity).toBeNull();
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
    await userEvent.click(screen.getByRole("button", { name: /use token/i }));
    await waitFor(() => expect(screen.getByText("inside")).toBeInTheDocument());
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

  it("asks for a join code, not a token, by default", () => {
    clearToken();
    render(<TokenGate><div>inside</div></TokenGate>);
    expect(screen.getByLabelText(/join code/i)).toBeInTheDocument();
  });

  it("joins with a code and shows the app", async () => {
    clearToken();
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(new Response(JSON.stringify({ token: "scpi_new", identity: "bob" }), { status: 200 }))
        .mockResolvedValueOnce(new Response(JSON.stringify({ identity: "bob" }), { status: 200 })),
    );
    render(<TokenGate><div>inside</div></TokenGate>);
    await userEvent.type(screen.getByLabelText(/join code/i), "417902");
    await userEvent.click(screen.getByRole("button", { name: /connect/i }));
    await waitFor(() => expect(screen.getByText("inside")).toBeInTheDocument());
    expect(getToken()).toBe("scpi_new");
  });

  it("accepts a code typed with a space, the way it is printed", async () => {
    clearToken();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ token: "scpi_new", identity: "bob" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ identity: "bob" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<TokenGate><div>inside</div></TokenGate>);
    await userEvent.type(screen.getByLabelText(/join code/i), "417 902");
    await userEvent.click(screen.getByRole("button", { name: /connect/i }));
    await waitFor(() => expect(screen.getByText("inside")).toBeInTheDocument());
  });

  it("reports a rejected code without blaming the user's token", async () => {
    clearToken();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "HTTPException", detail: "That code or link is not valid, or it has expired. Ask for a new one." }), { status: 401 })));
    render(<TokenGate><div>inside</div></TokenGate>);
    await userEvent.type(screen.getByLabelText(/join code/i), "000000");
    await userEvent.click(screen.getByRole("button", { name: /connect/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/not valid, or it has expired/i);
  });

  it("passes the rate-limit message through rather than inventing one", async () => {
    clearToken();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "HTTPException", detail: "Too many attempts. Wait a minute and try again." }), { status: 429 })));
    render(<TokenGate><div>inside</div></TokenGate>);
    await userEvent.type(screen.getByLabelText(/join code/i), "000000");
    await userEvent.click(screen.getByRole("button", { name: /connect/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/too many attempts/i);
  });

  it("still offers the raw token field for scripts and CI", () => {
    clearToken();
    render(<TokenGate><div>inside</div></TokenGate>);
    expect(screen.getByLabelText(/access token/i)).toBeInTheDocument();
  });

  it("tells a locked-out scientist who to ask, not what to type in a shell", () => {
    clearToken();
    render(<TokenGate><div>inside</div></TokenGate>);
    expect(screen.queryByText(/scpi-web token add/i)).not.toBeInTheDocument();
    expect(screen.getByText(/ask your lab admin/i)).toBeInTheDocument();
  });
});
