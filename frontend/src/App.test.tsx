import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { ScoredJob } from "./types";

function makeJob(overrides: Partial<ScoredJob>): ScoredJob {
  return {
    dedup_key: "hash:default",
    status: "scored",
    company: "Acme Robotics",
    normalized_posting: {
      title: "Backend Engineer",
      required_skills: [],
      nice_to_have_skills: [],
      min_years_experience: null,
      salary_min: null,
      salary_max: null,
      salary_currency: null,
      work_arrangement: "remote",
      description: "A backend engineering role.",
    },
    semantic_fit_result: {
      fit_tier: "strong",
      matched_skills: ["python"],
      missing_skills: [],
      reasoning: "n/a",
    },
    review_status: "pending",
    ...overrides,
  };
}

const jobA = makeJob({ dedup_key: "hash:a", company: "Acme Robotics" });
const jobB = makeJob({
  dedup_key: "hash:b",
  company: "Other Co",
  normalized_posting: { ...jobA.normalized_posting, title: "Platform Engineer" },
});

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => body,
  } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("fetches the queue on mount and renders the first job", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ jobs: [jobA, jobB] }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await screen.findByText("Backend Engineer");
    expect(screen.getByText("Acme Robotics")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/jobs/queue");
    expect(screen.getByText("2 jobs remaining")).toBeInTheDocument();
  });

  it("shows a message when the queue is empty", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ jobs: [] })));

    render(<App />);

    await screen.findByText("No jobs to review right now.");
  });

  it("swiping right calls PATCH with swiped_right and advances to the next job", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/jobs/queue") {
        return jsonResponse({ jobs: [jobA, jobB] });
      }
      if (url === `/jobs/${jobA.dedup_key}/status` && init?.method === "PATCH") {
        return jsonResponse({ ...jobA, review_status: "swiped_right" });
      }
      throw new Error(`Unexpected fetch call: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await screen.findByText("Backend Engineer");

    fireEvent.click(screen.getByRole("button", { name: /interested/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `/jobs/${jobA.dedup_key}/status`,
        expect.objectContaining({
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "swiped_right" }),
        }),
      );
    });

    await screen.findByText("Platform Engineer");
    expect(screen.getByText("1 job remaining")).toBeInTheDocument();
  });

  it("swiping left calls PATCH with swiped_left and advances to the next job", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/jobs/queue") {
        return jsonResponse({ jobs: [jobA, jobB] });
      }
      if (url === `/jobs/${jobA.dedup_key}/status` && init?.method === "PATCH") {
        return jsonResponse({ ...jobA, review_status: "swiped_left" });
      }
      throw new Error(`Unexpected fetch call: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await screen.findByText("Backend Engineer");

    fireEvent.click(screen.getByRole("button", { name: /pass/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `/jobs/${jobA.dedup_key}/status`,
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ status: "swiped_left" }),
        }),
      );
    });

    await screen.findByText("Platform Engineer");
  });

  it("shows an error message when the queue fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, false, 500)));

    render(<App />);

    await screen.findByText(/something went wrong/i);
  });
});
