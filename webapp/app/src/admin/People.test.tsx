import { render, screen, waitFor, within } from "@testing-library/react";
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

  it("names all three consequences of revoking before it happens", async () => {
    // Devices, live streams, and owned sessions are the three things
    // revoke_identity() actually tears down (scpi_control/server/revocation.py).
    // A colleague mid-capture loses their view and their session becomes
    // immediately claimable by anyone -- the confirmation must not undersell
    // that by mentioning only the device count.
    vi.spyOn(adminApi, "identities").mockResolvedValue([identity("bob", 2)]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([]);
    render(<People />);
    await userEvent.click(await screen.findByRole("button", { name: /revoke/i }));
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveTextContent(/device/i);
    expect(dialog).toHaveTextContent(/live stream/i);
    expect(dialog).toHaveTextContent(/session/i);
  });

  it("does not revoke until the confirmation is accepted", async () => {
    vi.spyOn(adminApi, "identities").mockResolvedValue([identity("bob", 2)]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([]);
    const revoke = vi.spyOn(adminApi, "revokeIdentity").mockResolvedValue({ devices: 2, streams: 1, sessions: 1 });
    render(<People />);
    await userEvent.click(await screen.findByRole("button", { name: /revoke/i }));
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(revoke).not.toHaveBeenCalled();
  });

  it("revokes the identity and reloads the roster when the confirmation is accepted", async () => {
    // The identities() stub returns bob on mount, then an empty list on the
    // reload that must follow a successful revoke. A local optimistic splice
    // (removing bob from state without calling the server again) would leave
    // the call count flat, so that assertion catches it even though the
    // screen would look right either way.
    const identities = vi
      .spyOn(adminApi, "identities")
      .mockResolvedValueOnce([identity("bob", 2)])
      .mockResolvedValueOnce([]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([]);
    const revoke = vi.spyOn(adminApi, "revokeIdentity").mockResolvedValue({ devices: 2, streams: 1, sessions: 1 });
    render(<People />);
    await screen.findByText(/bob/);
    const callsAfterMount = identities.mock.calls.length;

    await userEvent.click(screen.getByRole("button", { name: /revoke/i }));
    const dialog = screen.getByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /revoke/i }));

    expect(revoke).toHaveBeenCalledWith("bob");
    await waitFor(() => expect(identities.mock.calls.length).toBeGreaterThan(callsAfterMount));
    expect(await screen.findByText(/no one has access yet/i)).toBeInTheDocument();
  });

  it("surfaces the counts the revoke route returns", async () => {
    // revoke_identity() reports what it actually tore down -- the panel must
    // show that, not a generic "done" message, since the counts are the only
    // way an admin learns whether a live viewer or session was affected.
    vi.spyOn(adminApi, "identities")
      .mockResolvedValueOnce([identity("bob", 2)])
      .mockResolvedValueOnce([]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([]);
    vi.spyOn(adminApi, "revokeIdentity").mockResolvedValue({ devices: 2, streams: 1, sessions: 1 });
    render(<People />);
    await userEvent.click(await screen.findByRole("button", { name: /revoke/i }));
    const dialog = screen.getByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /revoke/i }));

    const notice = await screen.findByText(/2 devices/i);
    expect(notice).toHaveTextContent(/1 live stream/i);
    expect(notice).toHaveTextContent(/1 session/i);
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

  it("reloads invitations from the server after creating one", async () => {
    // invitations() returns nothing on mount, then the new invite on the
    // reload that must follow a successful create. If create only appended
    // the returned invitation to local state instead of reloading, the call
    // count would stay flat even though the row would still appear.
    vi.spyOn(adminApi, "identities").mockResolvedValue([]);
    const invitations = vi
      .spyOn(adminApi, "invitations")
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([invitation("a1", "bob")]);
    vi.spyOn(adminApi, "createInvitation").mockResolvedValue({ ...invitation("a1", "bob"), link: "http://192.168.1.50:8765/?invite=xyz" });
    render(<People />);
    await screen.findByLabelText(/name/i);
    const callsAfterMount = invitations.mock.calls.length;

    await userEvent.type(screen.getByLabelText(/name/i), "bob");
    await userEvent.click(screen.getByRole("button", { name: /invite/i }));

    await waitFor(() => expect(invitations.mock.calls.length).toBeGreaterThan(callsAfterMount));
    expect(await screen.findByRole("button", { name: /cancel invitation/i })).toBeInTheDocument();
  });

  it("cancels a pending invitation by id", async () => {
    vi.spyOn(adminApi, "identities").mockResolvedValue([]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([invitation("a1b2c3d4", "bob")]);
    const cancel = vi.spyOn(adminApi, "cancelInvitation").mockResolvedValue(undefined);
    render(<People />);
    await userEvent.click(await screen.findByRole("button", { name: /cancel invitation/i }));
    expect(cancel).toHaveBeenCalledWith("a1b2c3d4");
  });

  it("reloads invitations from the server after cancelling one", async () => {
    // invitations() returns bob's pending invite on mount, then an empty
    // list on the reload that must follow a successful cancel. A local
    // splice would leave the call count flat even though the row would
    // still disappear.
    vi.spyOn(adminApi, "identities").mockResolvedValue([]);
    const invitations = vi
      .spyOn(adminApi, "invitations")
      .mockResolvedValueOnce([invitation("a1b2c3d4", "bob")])
      .mockResolvedValueOnce([]);
    vi.spyOn(adminApi, "cancelInvitation").mockResolvedValue(undefined);
    render(<People />);
    await screen.findByRole("button", { name: /cancel invitation/i });
    const callsAfterMount = invitations.mock.calls.length;

    await userEvent.click(screen.getByRole("button", { name: /cancel invitation/i }));

    await waitFor(() => expect(invitations.mock.calls.length).toBeGreaterThan(callsAfterMount));
    await waitFor(() => expect(screen.queryByRole("button", { name: /cancel invitation/i })).not.toBeInTheDocument());
  });

  it("re-shows a pending invitation's code without re-creating it", async () => {
    // The code is what the admin reads down a phone, and the panel is the only
    // way to get it back: the CLI prints once and forgets, and the link cannot
    // be reconstructed because only its hash is stored. GET /api/invitations
    // returns the code for exactly this reason, so a listing that renders the
    // name and countdown but drops the code makes that response pointless and
    // leaves "cancel and re-invite" as the only remedy for a mislaid code.
    // This asserts a *pending* invitation loaded on mount -- not one this
    // browser session just created, which is a different code path.
    vi.spyOn(adminApi, "identities").mockResolvedValue([]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([invitation("a1b2c3d4", "bob")]);
    const create = vi.spyOn(adminApi, "createInvitation");
    render(<People />);
    expect(await screen.findByText(/417 902/)).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it("does not offer a link for a pending invitation, only a code", async () => {
    // Only the nonce's hash is stored, so the link genuinely exists once, at
    // creation. Rendering a link here would mean somebody had reconstructed
    // one -- which could only be a wrong one.
    vi.spyOn(adminApi, "identities").mockResolvedValue([]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([invitation("a1b2c3d4", "bob")]);
    render(<People />);
    await screen.findByText(/417 902/);
    expect(screen.queryByText(/\?invite=/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /copy link/i })).not.toBeInTheDocument();
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

  it("confirms a revoke in a modal that traps focus", async () => {
    // Same dialog as Sessions: the promise of aria-modal has to be true here too.
    vi.spyOn(adminApi, "identities").mockResolvedValue([identity("bob", 2)]);
    vi.spyOn(adminApi, "invitations").mockResolvedValue([]);
    const revoke = vi.spyOn(adminApi, "revokeIdentity");
    render(<People />);
    await userEvent.click(await screen.findByRole("button", { name: /revoke/i }));

    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(revoke).not.toHaveBeenCalled();
  });
});
