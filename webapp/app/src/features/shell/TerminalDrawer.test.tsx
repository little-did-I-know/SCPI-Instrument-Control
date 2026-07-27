import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TerminalDrawer } from "./TerminalDrawer";
import { useTerminalDrawer } from "./useTerminalDrawer";
import { setToken } from "../../api/token";
import { useSession } from "../../store/session";

const SESSION = { id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "SPD3303X", dialect: "", num_channels: 2, viewers: 0, owner: "", kind: "psu" as const };

beforeEach(() => {
  localStorage.clear();
  setToken("test-token");
  useSession.getState().clearSession();
  useSession.getState().setSession(SESSION);
  useTerminalDrawer.getState().close();
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("TerminalDrawer", () => {
  it("renders nothing while closed", () => {
    const { container } = render(<TerminalDrawer />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the SCPI console when open", () => {
    useTerminalDrawer.getState().toggle();
    render(<TerminalDrawer />);
    expect(screen.getByRole("region", { name: "SCPI terminal" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/scpi command/i)).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    useTerminalDrawer.getState().toggle();
    render(<TerminalDrawer />);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("region", { name: "SCPI terminal" })).not.toBeInTheDocument();
  });
});
