import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { JobCard } from "./JobCard";
import type { JobDetail, ScoredJob } from "../types";

const baseJob: ScoredJob = {
  dedup_key: "hash:abc123",
  status: "scored",
  company: "Acme Robotics",
  normalized_posting: {
    title: "Senior Backend Engineer",
    required_skills: ["python", "fastapi"],
    nice_to_have_skills: ["kafka"],
    min_years_experience: 5,
    salary_min: 150000,
    salary_max: 185000,
    salary_currency: "USD",
    work_arrangement: "remote",
    description: "Own our backend service architecture end to end.",
  },
  semantic_fit_result: {
    fit_tier: "strong",
    matched_skills: ["python", "fastapi", "docker"],
    missing_skills: ["kafka"],
    reasoning: "Meets all required skills; missing only the nice-to-have Kafka.",
  },
  review_status: "pending",
};

const baseDetail: JobDetail = {
  ...baseJob,
  gap_analysis_result: {
    gaps: [
      {
        skill: "kafka",
        classification: "fixable",
        reasoning: "Has hands-on experience with comparable message queue systems.",
      },
    ],
  },
  resume_optimization_result: {
    suggestions: [
      {
        skill: "kafka",
        edit_type: "rephrase",
        before: "Built an event-driven pipeline using RabbitMQ.",
        after: "Built an event-driven pipeline using RabbitMQ, directly transferable to Kafka.",
        rationale: "Surfaces existing message-queue experience in Kafka-relevant terms.",
      },
    ],
  },
};

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

describe("JobCard", () => {
  it("renders title, company, fit tier, salary, work arrangement, and matched/missing skills", () => {
    render(<JobCard job={baseJob} onSwipeLeft={vi.fn()} onSwipeRight={vi.fn()} />);

    expect(screen.getByText("Senior Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Acme Robotics")).toBeInTheDocument();
    expect(screen.getByText(/strong fit/i)).toBeInTheDocument();
    expect(screen.getByText("USD 150,000 - 185,000")).toBeInTheDocument();
    expect(screen.getByText("remote")).toBeInTheDocument();
    expect(screen.getByText("docker")).toBeInTheDocument();
    expect(screen.getByText("kafka")).toBeInTheDocument();
  });

  it("shows a fallback when no salary is specified", () => {
    const jobWithoutSalary: ScoredJob = {
      ...baseJob,
      normalized_posting: { ...baseJob.normalized_posting, salary_min: null, salary_max: null },
    };

    render(<JobCard job={jobWithoutSalary} onSwipeLeft={vi.fn()} onSwipeRight={vi.fn()} />);

    expect(screen.getByText("Not specified")).toBeInTheDocument();
  });

  it("shows a fallback when there is no semantic fit result yet", () => {
    const jobWithoutFit: ScoredJob = { ...baseJob, semantic_fit_result: null };

    render(<JobCard job={jobWithoutFit} onSwipeLeft={vi.fn()} onSwipeRight={vi.fn()} />);

    expect(screen.queryByText(/fit$/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("None")).toHaveLength(2);
  });

  it("calls onSwipeRight when Interested is clicked", () => {
    const onSwipeRight = vi.fn();
    render(<JobCard job={baseJob} onSwipeLeft={vi.fn()} onSwipeRight={onSwipeRight} />);

    fireEvent.click(screen.getByRole("button", { name: /interested/i }));

    expect(onSwipeRight).toHaveBeenCalledTimes(1);
  });

  it("calls onSwipeLeft when Pass is clicked", () => {
    const onSwipeLeft = vi.fn();
    render(<JobCard job={baseJob} onSwipeLeft={onSwipeLeft} onSwipeRight={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /pass/i }));

    expect(onSwipeLeft).toHaveBeenCalledTimes(1);
  });

  it("disables both buttons while a decision is pending", () => {
    render(
      <JobCard job={baseJob} onSwipeLeft={vi.fn()} onSwipeRight={vi.fn()} disabled />,
    );

    expect(screen.getByRole("button", { name: /interested/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /pass/i })).toBeDisabled();
  });

  it("does not fetch job detail until View Details is clicked", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<JobCard job={baseJob} onSwipeLeft={vi.fn()} onSwipeRight={vi.fn()} />);

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.queryByText(/full description/i)).not.toBeInTheDocument();
  });

  it("expands to fetch and show the full detail when View Details is clicked", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(baseDetail));
    vi.stubGlobal("fetch", fetchMock);

    render(<JobCard job={baseJob} onSwipeLeft={vi.fn()} onSwipeRight={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /view details/i }));

    expect(fetchMock).toHaveBeenCalledWith(`/jobs/${baseJob.dedup_key}`);

    await screen.findByText("Own our backend service architecture end to end.");
    expect(screen.getByText(/kafka: fixable/i)).toBeInTheDocument();
    expect(
      screen.getByText("Has hands-on experience with comparable message queue systems."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Built an event-driven pipeline using RabbitMQ."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Built an event-driven pipeline using RabbitMQ, directly transferable to Kafka.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Surfaces existing message-queue experience in Kafka-relevant terms."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /hide details/i })).toBeInTheDocument();
  });

  it("collapses the detail view when Hide Details is clicked, without re-fetching", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(baseDetail));
    vi.stubGlobal("fetch", fetchMock);

    render(<JobCard job={baseJob} onSwipeLeft={vi.fn()} onSwipeRight={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /view details/i }));
    await screen.findByText("Own our backend service architecture end to end.");

    fireEvent.click(screen.getByRole("button", { name: /hide details/i }));

    expect(screen.queryByText(/full description/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view details/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /view details/i }));
    await screen.findByText("Own our backend service architecture end to end.");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('shows "No resume suggestions for this posting" when there are no optimization suggestions', async () => {
    const detailWithoutSuggestions: JobDetail = {
      ...baseDetail,
      resume_optimization_result: { suggestions: [] },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detailWithoutSuggestions)));

    render(<JobCard job={baseJob} onSwipeLeft={vi.fn()} onSwipeRight={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /view details/i }));

    await screen.findByText("No resume suggestions for this posting.");
  });

  it("shows a fallback when there are no gaps identified", async () => {
    const detailWithoutGaps: JobDetail = { ...baseDetail, gap_analysis_result: { gaps: [] } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detailWithoutGaps)));

    render(<JobCard job={baseJob} onSwipeLeft={vi.fn()} onSwipeRight={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /view details/i }));

    await screen.findByText("No skill gaps identified for this posting.");
  });

  it("shows an error message when the detail fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, false, 500)));

    render(<JobCard job={baseJob} onSwipeLeft={vi.fn()} onSwipeRight={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /view details/i }));

    await screen.findByText(/failed to load details/i);
  });

  it("keeps Pass and Interested clickable while the detail view is expanded", async () => {
    const onSwipeRight = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(baseDetail)));

    render(<JobCard job={baseJob} onSwipeLeft={vi.fn()} onSwipeRight={onSwipeRight} />);
    fireEvent.click(screen.getByRole("button", { name: /view details/i }));
    await screen.findByText("Own our backend service architecture end to end.");

    fireEvent.click(screen.getByRole("button", { name: /interested/i }));

    await waitFor(() => expect(onSwipeRight).toHaveBeenCalledTimes(1));
  });
});
