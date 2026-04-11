import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";


describe("App", () => {
  it("renders the shell heading", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "工程骨架已启动" })).toBeInTheDocument();
  });
});
