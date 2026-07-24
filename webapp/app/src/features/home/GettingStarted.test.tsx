import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GettingStarted } from "./GettingStarted";

describe("GettingStarted", () => {
  it("points to the authenticated OpenAPI schema instead of the disabled /docs UI", () => {
    render(<GettingStarted />);
    expect(screen.queryByRole("link", { name: "/docs" })).not.toBeInTheDocument();
    expect(screen.getByText(/\/api\/openapi\.json/)).toBeInTheDocument();
    expect(screen.getByText(/bearer token/i)).toBeInTheDocument();
    expect(screen.getByText(/interactive docs UI is disabled/i)).toBeInTheDocument();
  });
});
