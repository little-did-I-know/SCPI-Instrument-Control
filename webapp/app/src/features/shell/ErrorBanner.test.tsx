import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ErrorBanner } from "./ErrorBanner";
import { useSession } from "../../store/session";

const SESSION = { id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "SDS1104X-E", dialect: "legacy", num_channels: 4, viewers: 0, owner: "", kind: "scope" as const };

beforeEach(() => {
  useSession.getState().clearSession();
});
afterEach(() => vi.restoreAllMocks());

describe("ErrorBanner", () => {
  it("renders nothing when there is no error", () => {
    useSession.getState().setSession(SESSION);
    const { container } = render(<ErrorBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the detail of a session error", () => {
    // useStream writes this field on an error frame and on an unclean close.
    // Before this component existed, nothing read it: the user got a red dot
    // and no explanation.
    useSession.getState().setSession(SESSION);
    useSession.getState().setError("connection lost");
    render(<ErrorBanner />);
    expect(screen.getByRole("alert")).toHaveTextContent("connection lost");
  });

  it("shows a dropped stream", () => {
    useSession.getState().setSession(SESSION);
    useSession.getState().setError("stream disconnected");
    render(<ErrorBanner />);
    expect(screen.getByRole("alert")).toHaveTextContent("stream disconnected");
  });

  it("dismisses the message without claiming the session recovered", async () => {
    // THE point of dismissError. setError(null) would flip status back to
    // "connected", so closing a message would make the UI claim the
    // connection came back. The message is the user's to dismiss; the
    // connection state is the instrument's to report.
    useSession.getState().setSession(SESSION);
    useSession.getState().setError("connection lost");
    render(<ErrorBanner />);
    await userEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(useSession.getState().status).toBe("error");
    expect(useSession.getState().error).toBeNull();
  });

  it("clears itself when a new session starts", () => {
    useSession.getState().setSession(SESSION);
    useSession.getState().setError("connection lost");
    useSession.getState().setSession({ ...SESSION, id: "def" });
    render(<ErrorBanner />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
