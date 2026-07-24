import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { ExportButton } from "./ExportButton";
import { useSession } from "../../store/session";

const BASE = { run_state: "STOP", timebase: 0.001, trigger: { mode: "AUTO", source: "C1", level: 0, slope: "POS", coupling: "DC" } };

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "" });
});

describe("ExportButton", () => {
  it("links to the capture URL for enabled channels only", () => {
    useSession.getState().applyState({
      ...BASE,
      channels: {
        "1": { enabled: true, voltage_scale: 1, voltage_offset: 0, coupling: "DC", probe_ratio: 1 },
        "2": { enabled: false, voltage_scale: 1, voltage_offset: 0, coupling: "DC", probe_ratio: 1 },
        "3": { enabled: true, voltage_scale: 1, voltage_offset: 0, coupling: "DC", probe_ratio: 1 },
      },
    });
    render(<ExportButton />);
    const link = screen.getByRole("link", { name: /export csv/i });
    expect(link).toHaveAttribute("href", "/api/sessions/abc/scope/capture.csv?channels=1,3");
    expect(link).toHaveAttribute("download");
  });

  it("is disabled when no channel is enabled", () => {
    useSession.getState().applyState({ ...BASE, channels: { "1": { enabled: false, voltage_scale: 1, voltage_offset: 0, coupling: "DC", probe_ratio: 1 } } });
    render(<ExportButton />);
    expect(screen.getByText(/export csv/i).closest("a")).toBeNull();
  });
});
