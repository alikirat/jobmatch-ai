export type FitTier = "strong" | "moderate" | "weak";
export type WorkArrangement = "remote" | "hybrid" | "onsite" | "unknown";
export type PipelineStatus = "ats_gate_failed" | "scored";
export type ReviewStatus = "pending" | "swiped_right" | "swiped_left";

export interface NormalizedPosting {
  title: string;
  required_skills: string[];
  nice_to_have_skills: string[];
  min_years_experience: number | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  work_arrangement: WorkArrangement;
}

export interface SemanticFitResult {
  fit_tier: FitTier;
  matched_skills: string[];
  missing_skills: string[];
  reasoning: string;
}

/** Subset of PipelineResult (see agents/schemas.py) needed to render a swipe card. */
export interface ScoredJob {
  dedup_key: string;
  status: PipelineStatus;
  company: string;
  normalized_posting: NormalizedPosting;
  semantic_fit_result: SemanticFitResult | null;
  review_status: ReviewStatus;
}
