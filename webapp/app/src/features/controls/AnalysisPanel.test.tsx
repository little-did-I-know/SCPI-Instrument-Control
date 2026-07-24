import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnalysisPanel } from "./AnalysisPanel";
import { ApiError, api } from "../../api/client";
import type { FilterConfig, SpectrumConfig } from "../../api/types";
import { useSession } from "../../store/session";

const SPECTRUM: SpectrumConfig = { enabled: false, channel: 1, window: "hanning", db: true };
const FILTERS: FilterConfig[] = [
  { n: 1, source: 1, kind: "lowpass", cutoff_low: null, cutoff_high: null, order: 5, enabled: false },
  { n: 2, source: 1, kind: "lowpass", cutoff_low: null, cutoff_high: null, order: 5, enabled: false },
];

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "" });
  vi.spyOn(api, "getSpectrum").mockResolvedValue(SPECTRUM);
  vi.spyOn(api, "getFilters").mockResolvedValue(FILTERS);
});
afterEach(() => vi.restoreAllMocks());

describe("AnalysisPanel", () => {
  it("loads config and PATCHes a window change", async () => {
    const patch = vi.spyOn(api, "patchSpectrum").mockResolvedValue({ ...SPECTRUM, window: "flattop" });
    render(<AnalysisPanel />);
    await userEvent.selectOptions(await screen.findByLabelText("Spectrum window"), "flattop");
    await waitFor(() => expect(patch).toHaveBeenCalledWith("abc", { window: "flattop" }));
  });

  it("enables the spectrum", async () => {
    const patch = vi.spyOn(api, "patchSpectrum").mockResolvedValue({ ...SPECTRUM, enabled: true });
    render(<AnalysisPanel />);
    await userEvent.click(await screen.findByLabelText("Enable spectrum"));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("abc", { enabled: true }));
  });

  it("commits a filter cutoff on blur", async () => {
    const patch = vi.spyOn(api, "patchFilter").mockResolvedValue(FILTERS);
    render(<AnalysisPanel />);
    const field = await screen.findByLabelText("Filter 1 high cutoff (Hz)"); // lowpass shows the high cutoff
    await userEvent.type(field, "100");
    await userEvent.tab();
    await waitFor(() => expect(patch).toHaveBeenCalledWith("abc", 1, { cutoff_high: 100 }));
  });

  it("toggles a filter", async () => {
    const patch = vi.spyOn(api, "patchFilter").mockResolvedValue(FILTERS);
    render(<AnalysisPanel />);
    await userEvent.click(await screen.findByLabelText("Enable filter 1"));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("abc", 1, { enabled: true }));
  });

  it("surfaces a PATCH error", async () => {
    vi.spyOn(api, "patchFilter").mockRejectedValue(new ApiError(400, "InvalidParameterError", "lowpass requires cutoff_high"));
    render(<AnalysisPanel />);
    await userEvent.click(await screen.findByLabelText("Enable filter 1"));
    expect(await screen.findByRole("alert")).toHaveTextContent("lowpass requires cutoff_high");
  });
});
