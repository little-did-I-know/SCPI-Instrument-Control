import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppHeader } from "./AppHeader";
import { useTerminalDrawer } from "./useTerminalDrawer";
import { ApiError, api } from "../../api/client";
import { setToken } from "../../api/token";
import { useIdentity } from "../../store/identity";
import { useSession } from "../../store/session";

const SESSION = { id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "SDG1032X", dialect: "", num_channels: 2, viewers: 0, owner: "", kind: "awg" as const };

beforeEach(() => {
  localStorage.clear();
  setToken("test-token");
  useSession.getState().clearSession();
  useIdentity.getState().clearIdentity();
  useTerminalDrawer.getState().close();
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AppHeader", () => {
  it("names the instrument when there is a session", () => {
    useSession.getState().setSession(SESSION);
    render(<AppHeader />);
    expect(screen.getByText(/SDG1032X/)).toBeInTheDocument();
  });

  it("says there is no instrument when there is no session", () => {
    render(<AppHeader />);
    expect(screen.getByText("no instrument")).toBeInTheDocument();
  });

  it("offers no terminal toggle without a session", () => {
    render(<AppHeader />);
    expect(screen.queryByRole("button", { name: /terminal/i })).not.toBeInTheDocument();
  });

  it("offers the terminal toggle in a session and reports its state", async () => {
    // Note: one render() per test. Rendering AppHeader twice in a single test
    // would put two headers in the DOM and make every getByRole ambiguous.
    useSession.getState().setSession(SESSION);
    render(<AppHeader />);
    const toggle = screen.getByRole("button", { name: /terminal/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  it("points the toggle at the drawer it controls", () => {
    useSession.getState().setSession(SESSION);
    render(<AppHeader />);
    expect(screen.getByRole("button", { name: /terminal/i })).toHaveAttribute("aria-controls");
  });
});

describe("AppHeader disconnect", () => {
  it("offers Disconnect in a session of any kind", () => {
    useSession.getState().setSession({ ...SESSION, kind: "psu" });
    render(<AppHeader />);
    expect(screen.getByRole("button", { name: /disconnect/i })).toBeInTheDocument();
  });

  it("does not offer Disconnect with no session", () => {
    render(<AppHeader />);
    expect(screen.queryByRole("button", { name: /disconnect/i })).not.toBeInTheDocument();
  });

  it("returns to disconnected even if the session is already gone (DELETE 404)", async () => {
    // Moved from ScopeToolbar.test.tsx: the behaviour is unchanged, only its
    // home is. A session may already be gone server-side, and the user must
    // still end up disconnected locally.
    vi.spyOn(api, "deleteSession").mockRejectedValue(new ApiError(404, "HTTPException", "unknown session abc"));
    useSession.getState().setSession(SESSION);
    render(<AppHeader />);
    await userEvent.click(screen.getByRole("button", { name: /disconnect/i }));
    await waitFor(() => expect(useSession.getState().session).toBeNull());
    expect(useSession.getState().status).toBe("disconnected");
  });
});

describe("AppHeader ownership", () => {
  it("tells a non-owner their session is read-only", () => {
    useIdentity.getState().setIdentity("bob");
    useSession.getState().setSession({ ...SESSION, owner: "alice" });
    render(<AppHeader />);
    expect(screen.getByText(/read-only/i)).toBeInTheDocument();
    expect(screen.getByText(/alice/)).toBeInTheDocument();
  });

  it("shows the owner no ownership chrome at all", () => {
    useIdentity.getState().setIdentity("alice");
    useSession.getState().setSession({ ...SESSION, owner: "alice" });
    render(<AppHeader />);
    expect(screen.queryByText(/read-only/i)).not.toBeInTheDocument();
  });

  it("drops the read-only badge once the claim succeeds", async () => {
    useIdentity.getState().setIdentity("bob");
    useSession.getState().setSession({ ...SESSION, owner: "alice" });
    vi.spyOn(api, "claimSession").mockResolvedValue({ ...SESSION, owner: "bob" });
    vi.spyOn(api, "getSession").mockResolvedValue({ ...SESSION, owner: "bob" });
    render(<AppHeader />);
    await userEvent.click(screen.getByRole("button", { name: /claim/i }));
    await waitFor(() => expect(screen.queryByText(/read-only/i)).not.toBeInTheDocument());
  });

  it("does not leak an unhandled rejection when the post-claim refresh fails, and keeps the badge up with the failure reported", async () => {
    // The claim itself succeeds (claimSession resolves); the refresh that
    // would let the header stop claiming read-only fails. Two things must be
    // true: nothing escapes as an unhandled rejection (if it did, Vitest
    // itself attaches an "Unhandled Errors" failure to this test -- see the
    // finding's revert-verification for what that looks like), and the badge
    // staying up is the honest outcome here -- ownership could not be
    // re-confirmed locally, and the server enforces it regardless of what
    // this tab shows.
    useIdentity.getState().setIdentity("bob");
    useSession.getState().setSession({ ...SESSION, owner: "alice" });
    vi.spyOn(api, "claimSession").mockResolvedValue({ ...SESSION, owner: "bob" });
    vi.spyOn(api, "getSession").mockRejectedValue(new ApiError(500, "Error", "could not refresh session"));
    render(<AppHeader />);
    await userEvent.click(screen.getByRole("button", { name: /claim/i }));
    await waitFor(() => expect(useSession.getState().error).toBe("could not refresh session"));
    expect(screen.getByText(/read-only/i)).toBeInTheDocument();
    expect(screen.getByText(/alice/)).toBeInTheDocument();
  });

  it("keeps live instrument readings through a claim", async () => {
    // Claiming changes who owns the session, not what the instrument reads.
    // Blanking the readings would make the panel flash empty for a poll
    // interval over a change that has nothing to do with them.
    useIdentity.getState().setIdentity("bob");
    useSession.getState().setSession({ ...SESSION, owner: "alice" });
    useSession.getState().applyAwgState({ channels: [{ channel: 1, function: "SINE", frequency: 1000, amplitude: 2, offset: 0, phase: 0, enabled: true, duty_cycle: null, symmetry: null }] });
    vi.spyOn(api, "claimSession").mockResolvedValue({ ...SESSION, owner: "bob" });
    vi.spyOn(api, "getSession").mockResolvedValue({ ...SESSION, owner: "bob" });
    render(<AppHeader />);
    await userEvent.click(screen.getByRole("button", { name: /claim/i }));
    await waitFor(() => expect(useSession.getState().session?.owner).toBe("bob"));
    expect(useSession.getState().awg?.channels).toHaveLength(1);
  });
});
