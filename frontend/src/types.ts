export type FitTier = "strong" | "moderate" | "weak";
export type WorkArrangement = "remote" | "hybrid" | "onsite" | "unknown";
export type PipelineStatus = "ats_gate_failed" | "scored";
export type ReviewStatus = "pending" | "swiped_right" | "swiped_left";

export type GapClassification = "fixable" | "real_gap" | "borderline";
export type ResumeEditType = "rephrase" | "reorder";

export interface NormalizedPosting {
  title: string;
  required_skills: string[];
  nice_to_have_skills: string[];
  min_years_experience: number | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  work_arrangement: WorkArrangement;
  description: string | null;
}

export interface SemanticFitResult {
  fit_tier: FitTier;
  matched_skills: string[];
  missing_skills: string[];
  reasoning: string;
}

export interface SkillGap {
  skill: string;
  classification: GapClassification;
  reasoning: string;
}

export interface GapAnalysisResult {
  gaps: SkillGap[];
}

export interface ResumeEditSuggestion {
  skill: string;
  edit_type: ResumeEditType;
  before: string;
  after: string;
  rationale: string;
}

export interface ResumeOptimizationResult {
  suggestions: ResumeEditSuggestion[];
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

/** Full PipelineResult, fetched on demand for the expanded job card detail view. */
export interface JobDetail extends ScoredJob {
  gap_analysis_result: GapAnalysisResult | null;
  resume_optimization_result: ResumeOptimizationResult | null;
}
