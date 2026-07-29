import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmDialog } from "./ConfirmDialog";

function setup(overrides: Partial<React.ComponentProps<typeof ConfirmDialog>> = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(<ConfirmDialog title="Close bench?" body="This ends the session." confirmLabel="Close" onConfirm={onConfirm} onCancel={onCancel} {...overrides} />);
  return { onConfirm, onCancel };
}

describe("ConfirmDialog", () => {
  it("names itself and renders its body and actions", () => {
    setup();
    const dialog = screen.getByRole("alertdialog", { name: "Close bench?" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText("This ends the session.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });

  it("focuses Cancel, not the confirming action", () => {
    // A destructive confirmation should treat a stray Enter as "cancel".
    setup();
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  it("cancels on Escape", async () => {
    const { onCancel } = setup();
    await userEvent.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("cancels on a backdrop click", async () => {
    const { onCancel } = setup();
    await userEvent.click(screen.getByTestId("confirm-backdrop"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("does not cancel on a click inside the panel", async () => {
    const { onCancel } = setup();
    await userEvent.click(screen.getByText("This ends the session."));
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("ignores Escape and backdrop clicks while busy", async () => {
    // A half-dismissed dialog during a slow close would leave the operator
    // unsure whether the action went through.
    const { onCancel } = setup({ busy: true });
    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByTestId("confirm-backdrop"));
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("confirms when the confirming action is pressed", async () => {
    const { onConfirm } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("keeps Tab inside the dialog", async () => {
    setup();
    const cancel = screen.getByRole("button", { name: "Cancel" });
    const confirm = screen.getByRole("button", { name: "Close" });
    expect(cancel).toHaveFocus();
    await userEvent.tab();
    expect(confirm).toHaveFocus();
    await userEvent.tab();
    expect(cancel).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(confirm).toHaveFocus();
  });

  it("returns focus to whatever opened it", async () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>Open</button>
          {open ? <ConfirmDialog title="Close bench?" body="body" confirmLabel="Close" onConfirm={() => setOpen(false)} onCancel={() => setOpen(false)} /> : null}
        </>
      );
    }
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open" });
    await userEvent.click(opener);
    await userEvent.keyboard("{Escape}");
    expect(opener).toHaveFocus();
  });
});
