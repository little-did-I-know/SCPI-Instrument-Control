import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OwnerBadge } from "./OwnerBadge";

const session = { id: "s1", label: "scope", owner: "robin", mock: true } as never;

describe("OwnerBadge", () => {
  it("shows nothing intrusive when you are the owner", () => {
    render(<OwnerBadge session={session} identity="robin" onClaimed={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /claim/i })).not.toBeInTheDocument();
  });

  it("marks the session read-only for a non-owner", () => {
    render(<OwnerBadge session={session} identity="someone-else" onClaimed={vi.fn()} />);
    expect(screen.getByText(/read-only/i)).toBeInTheDocument();
    expect(screen.getByText(/robin/)).toBeInTheDocument();
  });

  it("offers a claim button to a non-owner", () => {
    render(<OwnerBadge session={session} identity="someone-else" onClaimed={vi.fn()} />);
    expect(screen.getByRole("button", { name: /claim/i })).toBeInTheDocument();
  });
});
