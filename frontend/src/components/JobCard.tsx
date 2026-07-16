import { useCallback, useState } from "react";
import { fetchJobDetail } from "../api";
import type { JobDetail, ScoredJob } from "../types";

interface JobCardProps {
  job: ScoredJob;
  onSwipeLeft: () => void;
  onSwipeRight: () => void;
  disabled?: boolean;
}

function formatSalary(job: ScoredJob): string | null {
  const { salary_min, salary_max, salary_currency } = job.normalized_posting;
  if (salary_min == null && salary_max == null) {
    return null;
  }
  const currency = salary_currency ? `${salary_currency} ` : "";
  if (salary_min != null && salary_max != null) {
    return `${currency}${salary_min.toLocaleString()} - ${salary_max.toLocaleString()}`;
  }
  const value = salary_min ?? salary_max;
  return `${currency}${value!.toLocaleString()}`;
}

function SkillList({ title, skills }: { title: string; skills: string[] }) {
  return (
    <div className="job-card__skill-group">
      <h3>{title}</h3>
      {skills.length > 0 ? (
        <ul>
          {skills.map((skill) => (
            <li key={skill}>{skill}</li>
          ))}
        </ul>
      ) : (
        <p className="job-card__skill-empty">None</p>
      )}
    </div>
  );
}

function GapAnalysisSection({ detail }: { detail: JobDetail }) {
  const gaps = detail.gap_analysis_result?.gaps ?? [];

  return (
    <section className="job-card__gaps">
      <h3>Gap analysis</h3>
      {gaps.length > 0 ? (
        <ul>
          {gaps.map((gap) => (
            <li key={gap.skill}>
              <span className={`gap-classification gap-classification--${gap.classification}`}>
                {gap.skill}: {gap.classification.replace("_", " ")}
              </span>
              <p>{gap.reasoning}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="job-card__detail-empty">No skill gaps identified for this posting.</p>
      )}
    </section>
  );
}

function ResumeOptimizationSection({ detail }: { detail: JobDetail }) {
  const suggestions = detail.resume_optimization_result?.suggestions ?? [];

  return (
    <section className="job-card__optimizations">
      <h3>Resume suggestions</h3>
      {suggestions.length > 0 ? (
        <ul>
          {suggestions.map((suggestion, index) => (
            <li key={`${suggestion.skill}-${index}`}>
              <p className="job-card__suggestion-skill">{suggestion.skill}</p>
              <p>
                <strong>Before:</strong> {suggestion.before}
              </p>
              <p>
                <strong>After:</strong> {suggestion.after}
              </p>
              <p className="job-card__suggestion-rationale">{suggestion.rationale}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="job-card__detail-empty">No resume suggestions for this posting.</p>
      )}
    </section>
  );
}

export function JobCard({ job, onSwipeLeft, onSwipeRight, disabled = false }: JobCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const salary = formatSalary(job);
  const fitTier = job.semantic_fit_result?.fit_tier;
  const matchedSkills = job.semantic_fit_result?.matched_skills ?? [];
  const missingSkills = job.semantic_fit_result?.missing_skills ?? [];

  const handleToggleExpanded = useCallback(() => {
    setExpanded((wasExpanded) => {
      const nowExpanded = !wasExpanded;
      if (nowExpanded && !detail && !loadingDetail) {
        setLoadingDetail(true);
        setDetailError(null);
        fetchJobDetail(job.dedup_key)
          .then(setDetail)
          .catch((err: Error) => setDetailError(err.message))
          .finally(() => setLoadingDetail(false));
      }
      return nowExpanded;
    });
  }, [detail, loadingDetail, job.dedup_key]);

  return (
    <div className="job-card">
      <div className="job-card__header">
        <h2>{job.normalized_posting.title}</h2>
        <p className="job-card__company">{job.company}</p>
        {fitTier && <span className={`fit-tier fit-tier--${fitTier}`}>{fitTier} fit</span>}
      </div>

      <dl className="job-card__meta">
        <div>
          <dt>Salary</dt>
          <dd>{salary ?? "Not specified"}</dd>
        </div>
        <div>
          <dt>Work arrangement</dt>
          <dd>{job.normalized_posting.work_arrangement}</dd>
        </div>
      </dl>

      <div className="job-card__skills">
        <SkillList title="Matched skills" skills={matchedSkills} />
        <SkillList title="Missing skills" skills={missingSkills} />
      </div>

      <button
        type="button"
        className="button button--details"
        onClick={handleToggleExpanded}
        aria-expanded={expanded}
      >
        {expanded ? "Hide Details" : "View Details"}
      </button>

      {expanded && (
        <div className="job-card__details">
          {loadingDetail && <p>Loading details…</p>}
          {detailError && (
            <p className="job-card__detail-error">Failed to load details: {detailError}</p>
          )}
          {detail && (
            <>
              <section className="job-card__description">
                <h3>Full description</h3>
                <p>{detail.normalized_posting.description ?? "No description available."}</p>
              </section>

              <GapAnalysisSection detail={detail} />
              <ResumeOptimizationSection detail={detail} />
            </>
          )}
        </div>
      )}

      <div className="job-card__actions">
        <button
          type="button"
          className="button button--pass"
          onClick={onSwipeLeft}
          disabled={disabled}
        >
          Pass
        </button>
        <button
          type="button"
          className="button button--interested"
          onClick={onSwipeRight}
          disabled={disabled}
        >
          Interested
        </button>
      </div>
    </div>
  );
}
