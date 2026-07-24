import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { ScreenshotButton } from "./ScreenshotButton";
import { useSession } from "../../store/session";

beforeEach(() => useSession.getState().clearSession());

describe("ScreenshotButton", () => {
  it("links to the screenshot URL when connected", () => {
    useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "" });
    render(<ScreenshotButton />);
    expect(screen.getByRole("link", { name: /screenshot/i })).toHaveAttribute("href", "/api/sessions/abc/scope/screenshot.png");
  });

  it("is not a link with no session", () => {
    render(<ScreenshotButton />);
    expect(screen.getByText(/screenshot/i).closest("a")).toBeNull();
  });
});
