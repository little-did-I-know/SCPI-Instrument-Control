import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ViewModeToggle } from "./ViewModeToggle";

describe("ViewModeToggle", () => {
  it("marks the current mode pressed and reports changes", async () => {
    const onChange = vi.fn();
    render(<ViewModeToggle value="Time" onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Time" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Spectrum" }));
    expect(onChange).toHaveBeenCalledWith("Spectrum");
  });
});
