import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TerminalPanel } from "./TerminalPanel";
import { api } from "../../api/client";
import { useSession } from "../../store/session";

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "", kind: "scope" });
});
afterEach(() => vi.restoreAllMocks());

describe("TerminalPanel", () => {
  it("sends a command and shows the response", async () => {
    vi.spyOn(api, "command").mockResolvedValue({ command: "*IDN?", response: "Siglent,SDS1104X-E,1,1" });
    render(<TerminalPanel />);

    await userEvent.type(screen.getByPlaceholderText(/scpi command/i), "*IDN?");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText(/Siglent,SDS1104X-E/)).toBeInTheDocument();
    expect(screen.getByText(/\*IDN\?/)).toBeInTheDocument();
  });

  it("renders a timeout error as an error line", async () => {
    const { ApiError } = await import("../../api/client");
    vi.spyOn(api, "command").mockRejectedValue(new ApiError(504, "SiglentTimeoutError", "no response for query: BOGUS?"));
    render(<TerminalPanel />);

    await userEvent.type(screen.getByPlaceholderText(/scpi command/i), "BOGUS?");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText(/no response for query/i)).toBeInTheDocument();
  });
});
