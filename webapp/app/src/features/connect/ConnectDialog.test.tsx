import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConnectDialog } from "./ConnectDialog";
import { api } from "../../api/client";

afterEach(() => vi.restoreAllMocks());

const DEVICE = { address: "192.168.1.50", idn: "Siglent Technologies,SDS824X HD,X,1", manufacturer: "Siglent Technologies", model: "SDS824X HD", dialect: "modern", kind: "scope", connected: false };
const SESSION = { id: "abc", label: "bench", mock: false, address: "192.168.1.50", state: "connected", idn: DEVICE.idn, model: "SDS824X HD", dialect: "modern", num_channels: 4 };

describe("ConnectDialog", () => {
  it("scans and connects to a discovered instrument", async () => {
    vi.spyOn(api, "discover").mockResolvedValue([DEVICE]);
    const createSession = vi.spyOn(api, "createSession").mockResolvedValue(SESSION);
    const onConnected = vi.fn();
    render(<ConnectDialog onConnected={onConnected} />);

    await userEvent.click(screen.getByRole("button", { name: /scan network/i }));
    await screen.findByText("192.168.1.50");
    await userEvent.click(screen.getByRole("button", { name: /^connect$/i }));

    await waitFor(() => expect(createSession).toHaveBeenCalledWith({ address: "192.168.1.50", label: "SDS824X HD" }));
    await waitFor(() => expect(onConnected).toHaveBeenCalledWith(SESSION));
  });

  it("connects a mock session without scanning", async () => {
    const createSession = vi.spyOn(api, "createSession").mockResolvedValue({ ...SESSION, mock: true, address: null });
    const onConnected = vi.fn();
    render(<ConnectDialog onConnected={onConnected} />);

    await userEvent.click(screen.getByRole("button", { name: /mock scope/i }));

    await waitFor(() => expect(createSession).toHaveBeenCalledWith({ mock: true }));
    await waitFor(() => expect(onConnected).toHaveBeenCalled());
  });

  it("shows the server's error detail when connect fails", async () => {
    const { ApiError } = await import("../../api/client");
    vi.spyOn(api, "createSession").mockRejectedValue(new ApiError(500, "SiglentConnectionError", "connection refused"));
    render(<ConnectDialog onConnected={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /mock scope/i }));

    expect(await screen.findByText(/connection refused/i)).toBeInTheDocument();
  });
});
