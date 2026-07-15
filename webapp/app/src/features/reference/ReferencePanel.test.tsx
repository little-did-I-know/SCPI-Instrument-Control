import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReferencePanel } from "./ReferencePanel";
import { api } from "../../api/client";
import type { ReferenceInfo } from "../../api/types";
import { useSession } from "../../store/session";

const REFS: ReferenceInfo[] = [{ name: "golden", channel: 1, timestamp: "2026-07-15T00:00:00", num_samples: 256, time_span: 0.25 }];
const OVERLAY = { name: "golden", channel: 1, t0: 0, dt: 1, points: [1] };

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0 });
});
afterEach(() => vi.restoreAllMocks());

describe("ReferencePanel", () => {
  it("saves the current trace as a named reference", async () => {
    vi.spyOn(api, "listReferences").mockResolvedValue([]);
    const save = vi.spyOn(api, "saveReference").mockResolvedValue(REFS);
    render(<ReferencePanel />);
    await userEvent.type(await screen.findByLabelText("Reference name"), "golden");
    await userEvent.click(screen.getByRole("button", { name: "Save reference" }));
    await waitFor(() => expect(save).toHaveBeenCalledWith("abc", "golden", 1));
    expect(await screen.findByText("golden")).toBeInTheDocument();
  });

  it("activates and deactivates a reference", async () => {
    vi.spyOn(api, "listReferences").mockResolvedValue(REFS);
    const put = vi.spyOn(api, "putReference").mockResolvedValue(OVERLAY);
    render(<ReferencePanel />);
    await userEvent.click(await screen.findByLabelText("Show golden"));
    expect(put).toHaveBeenCalledWith("abc", "golden");
    act(() => useSession.getState().applyReference({ name: "golden", channel: 1 })); // the broadcast lands
    await userEvent.click(await screen.findByLabelText("Hide golden"));
    expect(put).toHaveBeenLastCalledWith("abc", null);
  });

  it("deletes a reference and refreshes the list", async () => {
    const list = vi.spyOn(api, "listReferences").mockResolvedValueOnce(REFS).mockResolvedValueOnce([]);
    const del = vi.spyOn(api, "deleteReference").mockResolvedValue(undefined);
    render(<ReferencePanel />);
    await userEvent.click(await screen.findByLabelText("Delete golden"));
    await waitFor(() => expect(del).toHaveBeenCalledWith("abc", "golden"));
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  });

  it("shows comparison stats while a reference is active", async () => {
    vi.spyOn(api, "listReferences").mockResolvedValue(REFS);
    render(<ReferencePanel />);
    act(() => {
      useSession.getState().applyReference({ name: "golden", channel: 1 });
      useSession.getState().applyReferenceStats({ correlation: 0.987, max_deviation: 0.05 });
    });
    expect(await screen.findByText(/0\.987/)).toBeInTheDocument();
    expect(screen.getByText(/0\.05/)).toBeInTheDocument();
  });
});
