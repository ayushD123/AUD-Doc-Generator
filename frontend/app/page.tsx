"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import BorderGlow from "@/components/BorderGlow";
import {
  createProject,
  deleteProject,
  formatProjectDate,
  listProjects,
  type Project,
} from "@/lib/projects";

type ProjectForm = {
  customer_name: string;
  module_name: string;
  name: string;
  email_id: string;
};

const emptyForm: ProjectForm = {
  customer_name: "",
  module_name: "",
  name: "",
  email_id: "",
};

function optionalValue(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [form, setForm] = useState<ProjectForm>(emptyForm);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function refreshProjects() {
    setIsLoading(true);
    setMessage(null);

    try {
      setProjects(await listProjects());
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setMessage(`Unable to load projects: ${detail}`);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refreshProjects();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage(null);

    try {
      await createProject({
        customer_name: optionalValue(form.customer_name),
        module_name: optionalValue(form.module_name),
        name: optionalValue(form.name),
        email_id: optionalValue(form.email_id),
      });

      setForm(emptyForm);
      await refreshProjects();
      setMessage("Project created.");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setMessage(`Unable to create project: ${detail}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteProject(project: Project) {
    const projectLabel =
      project.customer_name || project.module_name || project.name || "this project";
    const confirmed = window.confirm(
      `Delete ${projectLabel}? This removes the project and its related records.`,
    );

    if (!confirmed) {
      return;
    }

    setDeletingProjectId(project.id);
    setMessage(null);

    try {
      await deleteProject(project.id);
      setProjects((current) => current.filter((item) => item.id !== project.id));
      setMessage("Project deleted.");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setMessage(`Unable to delete project: ${detail}`);
    } finally {
      setDeletingProjectId(null);
    }
  }

  return (
    <main className="page-shell workspace-page">
      <section className="workspace-panel" aria-labelledby="app-title">
        <header className="intro">
          <h1 id="app-title">AUD Generator</h1>
          <p className="subtitle">Internal Oracle AUD generation workspace</p>
        </header>

        <BorderGlow animated className="panel-glow">
          <section className="panel" aria-labelledby="create-project-title">
            <div className="section-heading">
              <h2 id="create-project-title">Create Project</h2>
            </div>

            <form className="project-form" onSubmit={handleSubmit}>
              <label>
                <span>Customer Name</span>
                <input
                  value={form.customer_name}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      customer_name: event.target.value,
                    }))
                  }
                />
              </label>

              <label>
                <span>Module Name</span>
                <input
                  value={form.module_name}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      module_name: event.target.value,
                    }))
                  }
                />
              </label>

              <label>
                <span>Author Name</span>
                <input
                  value={form.name}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                />
              </label>

              <label>
                <span>Email Id</span>
                <input
                  type="email"
                  value={form.email_id}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      email_id: event.target.value,
                    }))
                  }
                />
              </label>

              <div className="form-actions">
                <button
                  type="submit"
                  className="primary-button"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Creating..." : "Create Project"}
                </button>
              </div>
            </form>
          </section>
        </BorderGlow>

        {message ? <p className="status-message">{message}</p> : null}

        <section className="project-list-section" aria-labelledby="project-list-title">
          <div className="section-heading">
            <h2 id="project-list-title">Projects</h2>
            <button type="button" className="secondary-button" onClick={refreshProjects}>
              Refresh
            </button>
          </div>

          {isLoading ? <p className="muted-text">Loading projects...</p> : null}

          {!isLoading && projects.length === 0 ? (
            <p className="muted-text">No projects yet.</p>
          ) : null}

          <div className="project-list">
            {projects.map((project) => (
              <BorderGlow
                key={project.id}
                className="row-glow"
                glowRadius={18}
                glowIntensity={0.65}
              >
                <div className="project-row-shell">
                  <Link href={`/projects/${project.id}`} className="project-row">
                    <div>
                      <h3>{project.customer_name || "Unnamed customer"}</h3>
                      <p>{project.module_name || "No module selected"}</p>
                    </div>

                    <dl className="project-meta">
                      <div>
                        <dt>Status</dt>
                        <dd>{project.status}</dd>
                      </div>
                      <div>
                        <dt>Author Name</dt>
                        <dd>{project.name || "Not available"}</dd>
                      </div>
                      <div>
                        <dt>Created</dt>
                        <dd>{formatProjectDate(project.created_at)}</dd>
                      </div>
                    </dl>
                  </Link>
                  <button
                    type="button"
                    className="danger-button project-delete-button"
                    disabled={deletingProjectId === project.id}
                    onClick={() => void handleDeleteProject(project)}
                  >
                    {deletingProjectId === project.id ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </BorderGlow>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
