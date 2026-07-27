import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ManualConnect } from "./ManualConnect";

describe("ManualConnect", () => {
  it("connects the typed address", async () => {
    const onConnectAddress = vi.fn();
    render(<ManualConnect busy={false} onConnectAddress={onConnectAddress} onConnectMock={vi.fn()} onConnectMockPsu={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("IP address"), "192.168.1.50");
    await userEvent.click(screen.getByRole("button", { name: /^connect$/i }));
    expect(onConnectAddress).toHaveBeenCalledWith("192.168.1.50");
  });

  it("connects a mock scope", async () => {
    const onConnectMock = vi.fn();
    render(<ManualConnect busy={false} onConnectAddress={vi.fn()} onConnectMock={onConnectMock} onConnectMockPsu={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /mock scope/i }));
    expect(onConnectMock).toHaveBeenCalled();
  });

  it("connects a mock power supply", async () => {
    // The only no-hardware route to a PSU session: discovery finds nothing on
    // an empty bench, and the address field can only build a scope.
    const onConnectMockPsu = vi.fn();
    const onConnectMock = vi.fn();
    render(<ManualConnect busy={false} onConnectAddress={vi.fn()} onConnectMock={onConnectMock} onConnectMockPsu={onConnectMockPsu} />);
    await userEvent.click(screen.getByRole("button", { name: /mock power supply/i }));
    expect(onConnectMockPsu).toHaveBeenCalled();
    expect(onConnectMock).not.toHaveBeenCalled();
  });
});
