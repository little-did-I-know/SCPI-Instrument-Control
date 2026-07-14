import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Tabs } from "./Tabs";

const RAIL_TABS = ["Channels", "Trigger", "Measure", "Terminal"];

describe("Tabs", () => {
  it("renders every tab, including the last, as a real tab element", () => {
    render(<Tabs tabs={RAIL_TABS} value="Channels" onChange={() => {}} />);
    const tablist = screen.getByRole("tablist");
    const tabs = within(tablist).getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(RAIL_TABS);
  });

  it("wraps the tab strip so it cannot overflow a narrow rail", () => {
    // The rail is a fixed-width column; the strip must wrap to fit, never clip.
    render(<Tabs tabs={RAIL_TABS} value="Channels" onChange={() => {}} />);
    const tablist = screen.getByRole("tablist");
    expect(tablist.style.flexWrap).toBe("wrap");
    expect(tablist.style.maxWidth).toBe("100%");
  });

  it("selects a tab on click", async () => {
    const onChange = vi.fn();
    render(<Tabs tabs={RAIL_TABS} value="Channels" onChange={onChange} />);
    await userEvent.click(screen.getByRole("tab", { name: "Terminal" }));
    expect(onChange).toHaveBeenCalledWith("Terminal");
  });
});
