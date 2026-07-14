import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RecentBar } from "./RecentBar";
import * as recent from "./recent";

afterEach(() => vi.restoreAllMocks());

describe("RecentBar", () => {
  it("renders nothing when there are no recents", () => {
    vi.spyOn(recent, "getRecent").mockReturnValue([]);
    const { container } = render(<RecentBar onReconnect={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("reconnects the clicked recent entry", async () => {
    const entry = { address: "192.168.1.50", label: "SDS824X HD", kind: "scope", model: "SDS824X HD", mock: false };
    vi.spyOn(recent, "getRecent").mockReturnValue([entry]);
    const onReconnect = vi.fn();
    render(<RecentBar onReconnect={onReconnect} />);
    await userEvent.click(screen.getByRole("button", { name: "Reconnect SDS824X HD" }));
    expect(onReconnect).toHaveBeenCalledWith(entry);
  });
});
