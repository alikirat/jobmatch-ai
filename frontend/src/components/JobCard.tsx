import type { ScoredJob } from "../types";

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

export function JobCard({ job, onSwipeLeft, onSwipeRight, disabled = false }: JobCardProps) {
  const salary = formatSalary(job);
  const fitTier = job.semantic_fit_result?.fit_tier;
  const matchedSkills = job.semantic_fit_result?.matched_skills ?? [];
  const missingSkills = job.semantic_fit_result?.missing_skills ?? [];

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
