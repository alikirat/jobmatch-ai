import type { JobDetail, ReviewStatus, ScoredJob } from "./types";

export async function fetchJobsQueue(): Promise<ScoredJob[]> {
  const response = await fetch("/jobs/queue");
  if (!response.ok) {
    throw new Error(`Failed to fetch jobs queue (HTTP ${response.status})`);
  }
  const data = (await response.json()) as { jobs: ScoredJob[] };
  return data.jobs;
}

export async function fetchJobDetail(jobId: string): Promise<JobDetail> {
  const response = await fetch(`/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch job detail (HTTP ${response.status})`);
  }
  return (await response.json()) as JobDetail;
}

export async function updateJobStatus(
  jobId: string,
  status: Extract<ReviewStatus, "swiped_right" | "swiped_left">,
): Promise<void> {
  const response = await fetch(`/jobs/${jobId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!response.ok) {
    throw new Error(`Failed to update job status (HTTP ${response.status})`);
  }
}
