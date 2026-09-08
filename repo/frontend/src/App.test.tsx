import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "../src/App";

describe("stage 0 application shell", () => {
  it("shows the system name and API version", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "论文格式检测系统" }),
    ).toBeInTheDocument();
    expect(screen.getByText("API v1")).toBeInTheDocument();
  });

  it("shows the backend health placeholder", () => {
    render(<App />);

    expect(screen.getByText("后端服务待连接")).toBeInTheDocument();
  });
});
