"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { formatProjectDate, getProject, type Project } from "@/lib/projects";

const placeholderSections = [
  "Uploaded Files",
  "Jobs",
  "AUD Plan",
  "Generated Documents",
];

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    async function loadProject() {
      setIsLoading(true);
      setMessage(null);

      try {
        setProject(await getProject(params.projectId));
      } catch (error) {
        const detail = error instanceof Error ? error.message : "Unknown error.";
        setMessage(`Unable to load project: ${detail}`);
      } finally {
        setIsLoading(false);
      }
    }

    void loadProject();
  }, [params.projectId]);

  return (
    <main className="page-shell workspace-page">
      <section className="workspace-panel detail-panel" aria-labelledby="project-title">
        <Link href="/" className="back-link">
          Back to projects
        </Link>

        {isLoading ? <p className="muted-text">Loading project...</p> : null}

        {message ? <p className="status-message status-error">{message}</p> : null}

        {project ? (
          <>
            <header className="intro">
              <h1 id="project-title">{project.customer_name || "Unnamed customer"}</h1>
              <p className="subtitle">{project.module_name || "No module selected"}</p>
            </header>

            <section className="panel" aria-labelledby="metadata-title">
              <div className="section-heading">
                <h2 id="metadata-title">Project Metadata</h2>
              </div>

              <dl className="metadata-grid">
                <div>
                  <dt>Customer Name</dt>
                  <dd>{project.customer_name || "Not available"}</dd>
                </div>
                <div>
                  <dt>Module Name</dt>
                  <dd>{project.module_name || "Not available"}</dd>
                </div>
                <div>
                  <dt>Author Name</dt>
                  <dd>{project.name || "Not available"}</dd>
                </div>
                <div>
                  <dt>Email Id</dt>
                  <dd>{project.email_id || "Not available"}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{project.status}</dd>
                </div>
                <div>
                  <dt>Created</dt>
                  <dd>{formatProjectDate(project.created_at)}</dd>
                </div>
              </dl>
            </section>

            <section className="placeholder-grid" aria-label="Project workspace sections">
              {placeholderSections.map((section) => (
                <article key={section} className="placeholder-section">
                  <h2>{section}</h2>
                  <p>Not started</p>
                </article>
              ))}
            </section>
          </>
        ) : null}
      </section>
    </main>
  );
}
