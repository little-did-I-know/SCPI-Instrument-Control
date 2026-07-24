// webapp/app/src/features/controls/MathPanel.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MathPanel } from "./MathPanel";
import { api } from "../../api/client";
import { useSession } from "../../store/session";

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "" });
});
afterEach(() => vi.restoreAllMocks());

describe("MathPanel", () => {
  it("loads current math state and PATCHes an expression change", async () => {
    vi.spyOn(api, "getMath").mockResolvedValue([{ n: 1, expression: "", enabled: false }, { n: 2, expression: "", enabled: false }]);
    const patchMath = vi.spyOn(api, "patchMath").mockResolvedValue([{ n: 1, expression: "C1 - C2", enabled: false }, { n: 2, expression: "", enabled: false }]);
    render(<MathPanel />);
    const field = await screen.findByLabelText("Math 1 expression");
    await userEvent.type(field, "C1 - C2");
    await userEvent.tab();
    await waitFor(() => expect(patchMath).toHaveBeenCalledWith("abc", 1, { expression: "C1 - C2" }));
  });

  it("toggles enable", async () => {
    vi.spyOn(api, "getMath").mockResolvedValue([{ n: 1, expression: "C1", enabled: false }, { n: 2, expression: "", enabled: false }]);
    const patchMath = vi.spyOn(api, "patchMath").mockResolvedValue([{ n: 1, expression: "C1", enabled: true }, { n: 2, expression: "", enabled: false }]);
    render(<MathPanel />);
    await userEvent.click(await screen.findByLabelText("Enable math 1"));
    await waitFor(() => expect(patchMath).toHaveBeenCalledWith("abc", 1, { enabled: true }));
  });
});
