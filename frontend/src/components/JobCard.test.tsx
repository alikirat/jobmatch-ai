import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { JobCard } from "./JobCard";
import type { ScoredJob } from "../types";

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
  },
  semantic_fit_result: {
    fit_tier: "strong",
    matched_skills: ["python", "fastapi", "docker"],
    missing_skills: ["kafka"],
    reasoning: "Meets all required skills; missing only the nice-to-have Kafka.",
  },
  review_status: "pending",
};

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
});
