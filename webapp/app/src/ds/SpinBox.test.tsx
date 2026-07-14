import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SpinBox } from "./SpinBox";

describe("SpinBox", () => {
  it("puts the accessible name on the editable input, not the wrapper", () => {
    render(<SpinBox aria-label="V/div C1" value={0.5} onChange={() => {}} />);
    const field = screen.getByLabelText("V/div C1");
    expect(field.tagName).toBe("INPUT");
  });

  it("commits a typed value on blur through the labelled field", async () => {
    const onChange = vi.fn();
    render(<SpinBox aria-label="V/div C1" value={0.5} onChange={onChange} />);
    const field = screen.getByLabelText("V/div C1");
    await userEvent.clear(field);
    await userEvent.type(field, "2");
    await userEvent.tab();
    expect(onChange).toHaveBeenCalledWith(2);
  });
});
