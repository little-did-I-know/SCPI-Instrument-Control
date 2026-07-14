import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DeviceCard } from "./DeviceCard";
import type { DiscoveredDevice } from "../../api/types";

const scope = (over: Partial<DiscoveredDevice> = {}): DiscoveredDevice => ({
  address: "192.168.1.51", idn: "Siglent,SDS1104X-E,1,1", manufacturer: "Siglent", model: "SDS1104X-E", dialect: "legacy", kind: "scope", connected: false, ...over,
});

describe("DeviceCard", () => {
  it("free connectable scope shows Connect and fires onConnect", async () => {
    const onConnect = vi.fn();
    render(<DeviceCard device={scope()} variant="available" onConnect={onConnect} onOpen={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Connect SDS1104X-E" }));
    expect(onConnect).toHaveBeenCalledWith(scope());
  });

  it("connected device shows Open and fires onOpen", async () => {
    const device = scope({ connected: true, session_id: "abc", viewers: 2 });
    const onOpen = vi.fn();
    render(<DeviceCard device={device} variant="session" onConnect={vi.fn()} onOpen={onOpen} />);
    expect(screen.getByText(/2 viewers/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open SDS1104X-E" }));
    expect(onOpen).toHaveBeenCalledWith(device);
  });

  it("non-connectable kind shows a disabled coming-soon control", () => {
    const awg = scope({ kind: "awg", model: "SDG2042X", address: "192.168.1.60" });
    render(<DeviceCard device={awg} variant="available" onConnect={vi.fn()} onOpen={vi.fn()} />);
    expect(screen.getByText(/viewer coming soon/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /connect/i })).toBeNull();
  });

  it("disables the action while busy", () => {
    render(<DeviceCard device={scope()} variant="available" busy onConnect={vi.fn()} onOpen={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Connect SDS1104X-E" })).toBeDisabled();
  });
});
