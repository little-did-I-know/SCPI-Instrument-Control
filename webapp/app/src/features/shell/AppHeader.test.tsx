import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppHeader } from "./AppHeader";
import { useTerminalDrawer } from "./useTerminalDrawer";
import { setToken } from "../../api/token";
import { useSession } from "../../store/session";

const SESSION = { id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "SDG1032X", dialect: "", num_channels: 2, viewers: 0, owner: "", kind: "awg" as const };

beforeEach(() => {
  localStorage.clear();
  setToken("test-token");
  useSession.getState().clearSession();
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
