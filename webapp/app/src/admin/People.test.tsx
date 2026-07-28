import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { People } from "./People";
import { adminApi } from "./api";

const identity = (name: string, devices: number) => ({ name, devices, last_used: null });
const invitation = (id: string, name: string) => ({ id, name, code: "417902", expires: Date.now() / 1000 + 600 });

describe("People", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("lists identities with their device counts", async () => {
    vi.spyOn(adminApi, "identities").mockResolvedValue([identity("bob", 2)]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([]);
    render(<People />);
    expect(await screen.findByText(/bob/)).toBeInTheDocument();
    expect(screen.getByText(/2 devices/)).toBeInTheDocument();
  });

  it("names the consequence before revoking", async () => {
    // Revoking signs out every device that identity holds. The count is the
    // thing the CLI cannot easily tell you before you act, so the panel must.
    vi.spyOn(adminApi, "identities").mockResolvedValue([identity("bob", 2)]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([]);
    render(<People />);
    await userEvent.click(await screen.findByRole("button", { name: /revoke/i }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent(/all 2 of their devices/i);
  });

  it("does not revoke until the confirmation is accepted", async () => {
    vi.spyOn(adminApi, "identities").mockResolvedValue([identity("bob", 2)]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([]);
    const revoke = vi.spyOn(adminApi, "revokeIdentity").mockResolvedValue(undefined);
    render(<People />);
    await userEvent.click(await screen.findByRole("button", { name: /revoke/i }));
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(revoke).not.toHaveBeenCalled();
  });

  it("shows the link and the code after inviting", async () => {
    vi.spyOn(adminApi, "identities").mockResolvedValue([]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([]);
    vi.spyOn(adminApi, "createInvitation").mockResolvedValue({ ...invitation("a1", "bob"), link: "http://192.168.1.50:8765/?invite=xyz" });
    render(<People />);
    await userEvent.type(await screen.findByLabelText(/name/i), "bob");
    await userEvent.click(screen.getByRole("button", { name: /invite/i }));
    expect(await screen.findByText(/417 902/)).toBeInTheDocument();
    expect(screen.getByText(/\?invite=xyz/)).toBeInTheDocument();
  });

  it("cancels a pending invitation by id", async () => {
    vi.spyOn(adminApi, "identities").mockResolvedValue([]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([invitation("a1b2c3d4", "bob")]);
    const cancel = vi.spyOn(adminApi, "cancelInvitation").mockResolvedValue(undefined);
    render(<People />);
    await userEvent.click(await screen.findByRole("button", { name: /cancel invitation/i }));
    expect(cancel).toHaveBeenCalledWith("a1b2c3d4");
  });

  it("reports a failure instead of silently doing nothing", async () => {
    vi.spyOn(adminApi, "identities").mockResolvedValue([]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([]);
    vi.spyOn(adminApi, "createInvitation").mockRejectedValue(new Error("name must not be empty"));
    render(<People />);
    await userEvent.type(await screen.findByLabelText(/name/i), "x");
    await userEvent.click(screen.getByRole("button", { name: /invite/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/must not be empty/i);
  });

  it("shows the setup screen when nobody has access yet", async () => {
    vi.spyOn(adminApi, "identities").mockResolvedValue([]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([]);
    render(<People />);
    expect(await screen.findByText(/no one has access yet/i)).toBeInTheDocument();
  });
});
