import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ManualConnect } from "./ManualConnect";
import { KIND_META, type Kind } from "./kinds";

describe("ManualConnect", () => {
  it("connects the typed address", async () => {
    const onConnectAddress = vi.fn();
    render(<ManualConnect busy={false} onConnectAddress={onConnectAddress} onConnectMock={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("IP address"), "192.168.1.50");
    await userEvent.click(screen.getByRole("button", { name: /^connect$/i }));
    expect(onConnectAddress).toHaveBeenCalledWith("192.168.1.50");
  });

  it("connects a mock oscilloscope", async () => {
    const onConnectMock = vi.fn();
    render(<ManualConnect busy={false} onConnectAddress={vi.fn()} onConnectMock={onConnectMock} />);
    await userEvent.click(screen.getByRole("button", { name: `Mock ${KIND_META.scope.label}` }));
    expect(onConnectMock).toHaveBeenCalledWith("scope");
  });

  it("connects a mock power supply", async () => {
    // The only no-hardware route to a PSU session: discovery finds nothing on
    // an empty bench, and the address field can only build a scope.
    const onConnectMock = vi.fn();
    render(<ManualConnect busy={false} onConnectAddress={vi.fn()} onConnectMock={onConnectMock} />);
    await userEvent.click(screen.getByRole("button", { name: `Mock ${KIND_META.psu.label}` }));
    expect(onConnectMock).toHaveBeenCalledWith("psu");
  });

  it("connects a mock AWG", async () => {
    // Same reasoning as the scope/PSU cases above: without this button an AWG
    // session is unreachable on a bench with no hardware.
    const onConnectMock = vi.fn();
    render(<ManualConnect busy={false} onConnectAddress={vi.fn()} onConnectMock={onConnectMock} />);
    await userEvent.click(screen.getByRole("button", { name: `Mock ${KIND_META.awg.label}` }));
    expect(onConnectMock).toHaveBeenCalledWith("awg");
  });

  it("renders exactly one mock button per connectable kind in KIND_META, derived rather than hardcoded", () => {
    // A future kind marked connectable: true must get a mock button here with
    // zero changes to this file or to ManualConnect.tsx — that's the point.
    render(<ManualConnect busy={false} onConnectAddress={vi.fn()} onConnectMock={vi.fn()} />);
    const connectableKinds = (Object.keys(KIND_META) as Kind[]).filter((kind) => KIND_META[kind].connectable);
    expect(connectableKinds.length).toBeGreaterThan(0);
    for (const kind of connectableKinds) {
      expect(screen.getByRole("button", { name: `Mock ${KIND_META[kind].label}` })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("button", { name: /^Mock /})).toHaveLength(connectableKinds.length);
  });
});
