import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ManualConnect } from "./ManualConnect";

describe("ManualConnect", () => {
  it("connects the typed address", async () => {
    const onConnectAddress = vi.fn();
    render(<ManualConnect busy={false} onConnectAddress={onConnectAddress} onConnectMock={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("IP address"), "192.168.1.50");
    await userEvent.click(screen.getByRole("button", { name: /^connect$/i }));
    expect(onConnectAddress).toHaveBeenCalledWith("192.168.1.50");
  });

  it("connects a mock scope", async () => {
    const onConnectMock = vi.fn();
    render(<ManualConnect busy={false} onConnectAddress={vi.fn()} onConnectMock={onConnectMock} />);
    await userEvent.click(screen.getByRole("button", { name: /mock scope/i }));
    expect(onConnectMock).toHaveBeenCalled();
  });
});
