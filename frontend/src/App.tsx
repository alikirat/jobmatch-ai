import { useCallback, useEffect, useState } from "react";
import { fetchJobsQueue, updateJobStatus } from "./api";
import { JobCard } from "./components/JobCard";
import type { ScoredJob } from "./types";

function App() {
  const [jobs, setJobs] = useState<ScoredJob[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingDecision, setPendingDecision] = useState(false);

  const loadQueue = useCallback(() => {
    setError(null);
    fetchJobsQueue()
      .then(setJobs)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const handleSwipe = useCallback(
    async (status: "swiped_right" | "swiped_left") => {
      if (!jobs || jobs.length === 0) {
        return;
      }
      const [currentJob, ...rest] = jobs;
      setPendingDecision(true);
      setError(null);
      try {
        await updateJobStatus(currentJob.dedup_key, status);
        setJobs(rest);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setPendingDecision(false);
      }
    },
    [jobs],
  );

  return (
    <div className="app">
      <h1>JobMatch AI</h1>

      {error && <p className="app__error">Something went wrong: {error}</p>}

      {jobs === null && !error && <p>Loading jobs…</p>}

      {jobs !== null && jobs.length === 0 && <p>No jobs to review right now.</p>}

      {jobs !== null && jobs.length > 0 && (
        <>
          <JobCard
            key={jobs[0].dedup_key}
            job={jobs[0]}
            onSwipeLeft={() => handleSwipe("swiped_left")}
            onSwipeRight={() => handleSwipe("swiped_right")}
            disabled={pendingDecision}
          />
          <p className="app__remaining">
            {jobs.length} job{jobs.length === 1 ? "" : "s"} remaining
          </p>
        </>
      )}
    </div>
  );
}

export default App;
