import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeScreen } from "./HomeScreen";
import { api } from "../../api/client";
import type { DiscoveredDevice, SessionInfo } from "../../api/types";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

const SESSION: SessionInfo = { id: "abc", label: "bench", mock: false, address: "192.168.1.50", state: "connected", idn: "Siglent,SDS824X HD,1,1", model: "SDS824X HD", dialect: "modern", num_channels: 4, viewers: 0 };
const FREE: DiscoveredDevice = { address: "192.168.1.51", idn: "x", manufacturer: "Siglent", model: "SDS1104X-E", dialect: "legacy", kind: "scope", connected: false };

describe("HomeScreen", () => {
  it("shows discovered instruments and connects a free one", async () => {
    vi.spyOn(api, "listSessions").mockResolvedValue([]);
    vi.spyOn(api, "discover").mockResolvedValue([FREE]);
    const created = { ...SESSION, id: "new", address: "192.168.1.51", model: "SDS1104X-E" };
    const createSession = vi.spyOn(api, "createSession").mockResolvedValue(created);
    const onConnected = vi.fn();
    render(<HomeScreen onConnected={onConnected} />);

    await screen.findByRole("button", { name: "Connect SDS1104X-E" });
    await userEvent.click(screen.getByRole("button", { name: "Connect SDS1104X-E" }));

    await waitFor(() => expect(createSession).toHaveBeenCalledWith({ address: "192.168.1.51", label: "SDS1104X-E" }));
    await waitFor(() => expect(onConnected).toHaveBeenCalledWith(created));
  });

  it("seeds held sessions into the Your-sessions zone on mount", async () => {
    vi.spyOn(api, "listSessions").mockResolvedValue([SESSION]);
    vi.spyOn(api, "discover").mockResolvedValue([]);
    render(<HomeScreen onConnected={vi.fn()} />);
    await screen.findByRole("button", { name: "Open SDS824X HD" });
  });

  it("connects a mock scope from the rail", async () => {
    vi.spyOn(api, "listSessions").mockResolvedValue([]);
    vi.spyOn(api, "discover").mockResolvedValue([]);
    const createSession = vi.spyOn(api, "createSession").mockResolvedValue({ ...SESSION, mock: true, address: null });
    const onConnected = vi.fn();
    render(<HomeScreen onConnected={onConnected} />);
    await userEvent.click(await screen.findByRole("button", { name: /mock scope/i }));
    await waitFor(() => expect(createSession).toHaveBeenCalledWith({ mock: true }));
    await waitFor(() => expect(onConnected).toHaveBeenCalled());
  });

  it("surfaces a connect error detail", async () => {
    const { ApiError } = await import("../../api/client");
    vi.spyOn(api, "listSessions").mockResolvedValue([]);
    vi.spyOn(api, "discover").mockResolvedValue([FREE]);
    vi.spyOn(api, "createSession").mockRejectedValue(new ApiError(504, "SiglentTimeoutError", "connection timed out"));
    render(<HomeScreen onConnected={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Connect SDS1104X-E" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("connection timed out");
  });
});
