import { useEffect, useMemo, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

const terminalStates = new Set(["completed", "failed"]);
const statusLabels = {
  queued: "Queued",
  running: "Analyzing",
  completed: "Completed",
  failed: "Failed",
};

function nextProgress(status, previousProgress) {
  if (status === "queued") return Math.min(previousProgress + 4, 32);
  if (status === "running") return Math.min(previousProgress + 8, 92);
  if (status === "completed") return 100;
  if (status === "failed") return 100;
  return previousProgress;
}

function App() {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState([]);

  const activeJobIds = useMemo(
    () => jobs.filter((job) => !terminalStates.has(job.status)).map((job) => job.job_id),
    [jobs]
  );

  const handleUpload = async (event) => {
    event.preventDefault();
    setError("");

    if (!file) {
      setError("Please select a PDF file.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    setIsUploading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/jobs`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Upload failed.");
      }
      setJobs((prev) => [
        {
          job_id: data.job_id,
          status: data.status,
          progress: data.status === "queued" ? 12 : 20,
          createdAtMs: Date.now(),
        },
        ...prev,
      ]);
      setFile(null);
      event.target.reset();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  useEffect(() => {
    if (activeJobIds.length === 0) return undefined;

    const poll = async () => {
      const updates = await Promise.all(
        activeJobIds.map(async (jobId) => {
          const statusRes = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
          if (!statusRes.ok) {
            return { job_id: jobId, status: "failed", error_message: "Failed to fetch status." };
          }
          const statusData = await statusRes.json();
          if (statusData.status === "completed") {
            const resultRes = await fetch(`${API_BASE_URL}/jobs/${jobId}/result`);
            if (resultRes.ok) {
              const resultData = await resultRes.json();
              return { ...statusData, result: resultData.result };
            }
          }
          return statusData;
        })
      );

      setJobs((prev) => {
        return prev.map((job) => {
          const updated = updates.find((entry) => entry.job_id === job.job_id);
          const merged = updated ? { ...job, ...updated } : job;
          const prior = job.progress ?? 8;
          return { ...merged, progress: nextProgress(merged.status, prior) };
        });
      });
    };

    const timer = setInterval(poll, 2000);
    poll();
    return () => clearInterval(timer);
  }, [activeJobIds]);

  const totalJobs = jobs.length;
  const completedCount = jobs.filter((job) => job.status === "completed").length;
  const runningCount = jobs.filter((job) => !terminalStates.has(job.status)).length;
  const failedCount = jobs.filter((job) => job.status === "failed").length;

  return (
    <main className="container">
      <section className="hero">
        <h1>Consumer Sentiment Analyzer</h1>
        <p className="subtext">Upload a survey PDF and track asynchronous sentiment analysis jobs.</p>
        <div className="stats-grid">
          <article className="stat-card">
            <span>Total Jobs</span>
            <strong>{totalJobs}</strong>
          </article>
          <article className="stat-card">
            <span>In Progress</span>
            <strong>{runningCount}</strong>
          </article>
          <article className="stat-card">
            <span>Completed</span>
            <strong>{completedCount}</strong>
          </article>
          <article className="stat-card">
            <span>Failed</span>
            <strong>{failedCount}</strong>
          </article>
        </div>
      </section>

      <section className="upload-panel">
        <form className="upload-form" onSubmit={handleUpload}>
          <label className="file-control">
            <span>Select PDF</span>
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              disabled={isUploading}
            />
          </label>
          <span className="file-name">{file?.name || "No file selected"}</span>
          <button type="submit" disabled={isUploading}>
            {isUploading ? "Uploading..." : "Create Job"}
          </button>
        </form>

        {error && <p className="error">{error}</p>}
      </section>

      <section className="jobs">
        {jobs.length === 0 && <p className="empty-state">No jobs yet. Upload a PDF to start analysis.</p>}
        {jobs.map((job) => (
          <article key={job.job_id} className="card">
            <div className="job-header">
              <div className="row">
                <strong>Job ID:</strong> <code>{job.job_id}</code>
              </div>
              <span className={`status-pill ${job.status}`}>{statusLabels[job.status] || job.status}</span>
            </div>

            <div className="progress-track" aria-label={`Job ${job.job_id} progress`}>
              <div
                className={`progress-fill ${job.status}`}
                style={{ width: `${job.progress ?? 8}%` }}
              />
            </div>

            <div className="row progress-text">
              <span>{Math.round(job.progress ?? 8)}%</span>
              {!terminalStates.has(job.status) && <span className="pulse">Processing...</span>}
            </div>

            {job.error_message && <p className="error">Error: {job.error_message}</p>}

            {job.result && (
              <div className="result">
                <h3>Summary</h3>
                <p>{job.result.short_summary}</p>
                <p>
                  <strong>Overall Sentiment:</strong> {job.result.overall_sentiment}
                </p>
                <h4>Top Themes</h4>
                <ul>
                  {job.result.top_themes.map((theme) => (
                    <li key={theme.theme}>
                      {theme.theme} (evidence: {theme.evidence_feedback_ids.join(", ")})
                    </li>
                  ))}
                </ul>
                <h4>Recommended Actions</h4>
                <ul>
                  {job.result.recommended_actions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
                <p>
                  <strong>Uncertainty Note:</strong> {job.result.uncertainty_note}
                </p>
              </div>
            )}
          </article>
        ))}
      </section>
    </main>
  );
}

export default App;
