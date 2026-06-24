"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

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

type SortOption =
  | "newest"
  | "oldest"
  | "project-asc"
  | "project-desc"
  | "customer-asc"
  | "customer-desc";

function optionalValue(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function Icon({
  name,
  className,
}: {
  name:
    | "book"
    | "plus"
    | "folder"
    | "search"
    | "sort"
    | "refresh"
    | "trash"
    | "sun"
    | "moon";
  className?: string;
}) {
  if (name === "book") {
    return (
      <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4.5 5.2c0-.9.7-1.6 1.6-1.6h4.2c1 0 1.9.4 2.7 1.1v15.7c-.8-.7-1.7-1.1-2.7-1.1H5.7c-.7 0-1.2-.5-1.2-1.2Z" />
        <path d="M19.5 5.2c0-.9-.7-1.6-1.6-1.6h-4.2c-1 0-1.9.4-2.7 1.1v15.7c.8-.7 1.7-1.1 2.7-1.1h4.6c.7 0 1.2-.5 1.2-1.2Z" />
        <path d="M7.5 8h2.6M7.5 11h2.6M15 8h2M15 11h2" />
      </svg>
    );
  }

  const paths = {
    plus: <path d="M12 5v14M5 12h14" />,
    folder: (
      <path d="M3.8 7.2c0-1 .8-1.8 1.8-1.8h4l2 2.2h6.8c1 0 1.8.8 1.8 1.8v7.4c0 1-.8 1.8-1.8 1.8H5.6c-1 0-1.8-.8-1.8-1.8Z" />
    ),
    search: <path d="m20 20-4.4-4.4M10.8 17.2a6.4 6.4 0 1 1 0-12.8 6.4 6.4 0 0 1 0 12.8Z" />,
    sort: <path d="M7 4v13M4 14l3 3 3-3M17 20V7M14 10l3-3 3 3" />,
    refresh: <path d="M20 12a8 8 0 0 1-13.5 5.8M4 12A8 8 0 0 1 17.5 6.2M17.5 3.8v2.4h-2.4M6.5 20.2v-2.4h2.4" />,
    trash: <path d="M5 7h14M10 11v5M14 11v5M8 7l.7-2h6.6L16 7M7 7l.8 12h8.4L17 7" />,
    sun: (
      <>
        <path d="M12 3v2M12 19v2M5.6 5.6 7 7M17 17l1.4 1.4M3 12h2M19 12h2M5.6 18.4 7 17M17 7l1.4-1.4" />
        <path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z" />
      </>
    ),
    moon: <path d="M20.2 14.3A7.6 7.6 0 0 1 9.7 3.8 8.2 8.2 0 1 0 20.2 14.3Z" />,
    book: null,
  };

  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

type Theme = "light" | "dark";

const themeStorageKey = "audacle-theme";

function getProjectName(project: Project) {
  const customerName = project.customer_name?.trim();
  const moduleName = project.module_name?.trim();

  if (customerName && moduleName) {
    return `${customerName} - ${moduleName}`;
  }

  return customerName || moduleName || project.name || "Untitled project";
}

function compareText(left: string | null, right: string | null) {
  return (left || "").localeCompare(right || "", undefined, { sensitivity: "base" });
}

export default function Home() {
  const [theme, setTheme] = useState<Theme>("light");
  const [isThemeReady, setIsThemeReady] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [form, setForm] = useState<ProjectForm>(emptyForm);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortOption, setSortOption] = useState<SortOption>("newest");
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

  useEffect(() => {
    const storedTheme = window.localStorage.getItem(themeStorageKey);

    if (storedTheme === "light" || storedTheme === "dark") {
      setTheme(storedTheme);
    }

    setIsThemeReady(true);
  }, []);

  useEffect(() => {
    if (!isThemeReady) {
      return;
    }

    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem(themeStorageKey, theme);
  }, [isThemeReady, theme]);

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

  const displayedProjects = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    const filteredProjects = normalizedQuery
      ? projects.filter((project) =>
          [
            getProjectName(project),
            project.customer_name,
            project.module_name,
            project.name,
            project.email_id,
          ]
            .filter(Boolean)
            .some((value) => value!.toLowerCase().includes(normalizedQuery)),
        )
      : projects;

    return [...filteredProjects].sort((left, right) => {
      if (sortOption === "oldest" || sortOption === "newest") {
        const leftTime = left.created_at ? new Date(left.created_at).getTime() : 0;
        const rightTime = right.created_at ? new Date(right.created_at).getTime() : 0;
        return sortOption === "newest" ? rightTime - leftTime : leftTime - rightTime;
      }

      if (sortOption === "project-asc") {
        return compareText(getProjectName(left), getProjectName(right));
      }

      if (sortOption === "project-desc") {
        return compareText(getProjectName(right), getProjectName(left));
      }

      if (sortOption === "customer-asc") {
        return compareText(left.customer_name, right.customer_name);
      }

      return compareText(right.customer_name, left.customer_name);
    });
  }, [projects, searchQuery, sortOption]);

  return (
    <main className="audacle-dashboard" data-theme={theme}>
      <header className="dashboard-header">
        <div className="dashboard-header-inner">
          <div className="brand-lockup">
            <span className="brand-icon">
              <Icon name="book" />
            </span>
            <h1 id="app-title" className="brand-title">
              AUD<span>acle</span>
            </h1>
          </div>
          <div className="header-divider" aria-hidden="true" />
          <p className="header-subtitle">Application Understanding Document Generator</p>
          <div className="theme-toggle" role="group" aria-label="Choose display theme">
            <button
              type="button"
              className={theme === "light" ? "is-active" : undefined}
              aria-label="Switch to light mode"
              aria-pressed={theme === "light"}
              onClick={() => setTheme("light")}
            >
              <Icon name="sun" />
            </button>
            <button
              type="button"
              className={theme === "dark" ? "is-active" : undefined}
              aria-label="Switch to dark mode"
              aria-pressed={theme === "dark"}
              onClick={() => setTheme("dark")}
            >
              <Icon name="moon" />
            </button>
          </div>
        </div>
      </header>

      <section className="dashboard-container" aria-labelledby="app-title">
        <section className="hero-banner" aria-labelledby="welcome-title">
          <div className="hero-copy">
            <h2 id="welcome-title">
              Welcome to AUD<span>acle</span>
            </h2>
            <p>Create and manage Application Understanding Documents with ease.</p>
          </div>
          <div className="hero-illustration" aria-hidden="true">
            <div className="hero-panel-one" />
            <div className="hero-panel-two" />
            <div className="hero-document">
              <span />
              <span />
              <span />
              <span />
            </div>
            <div className="hero-block" />
          </div>
        </section>

        <section className="dashboard-card create-project-card" aria-labelledby="create-project-title">
          <div className="card-heading">
            <span className="card-icon">
              <Icon name="plus" />
            </span>
            <div>
              <h2 id="create-project-title">Create New Project</h2>
              <p>Provide the basic information to get started.</p>
            </div>
          </div>

          <form className="project-form dashboard-form" onSubmit={handleSubmit}>
            <label>
              <span>Customer Name</span>
              <input
                placeholder="Enter customer name"
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
                placeholder="Enter module name"
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
                placeholder="Enter author name"
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
                placeholder="Enter email address"
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
              <button type="submit" className="primary-button" disabled={isSubmitting}>
                <Icon name="plus" />
                {isSubmitting ? "Creating..." : "Create Project"}
              </button>
            </div>
          </form>
        </section>

        {message ? <p className="status-message dashboard-alert">{message}</p> : null}

        <section className="dashboard-card projects-card" aria-labelledby="project-list-title">
          <div className="projects-card-header">
            <div className="card-heading">
              <span className="card-icon">
                <Icon name="folder" />
              </span>
              <div>
                <h2 id="project-list-title">Projects</h2>
                <p>View and manage your projects.</p>
              </div>
            </div>

            <div className="projects-toolbar" aria-label="Project list controls">
              <label className="toolbar-search">
                <span className="sr-only">Search projects</span>
                <Icon name="search" />
                <input
                  value={searchQuery}
                  placeholder="Search projects..."
                  onChange={(event) => setSearchQuery(event.target.value)}
                />
              </label>

              <label className="toolbar-select">
                <span className="sr-only">Sort projects</span>
                <Icon name="sort" />
                <select
                  value={sortOption}
                  onChange={(event) => setSortOption(event.target.value as SortOption)}
                >
                  <option value="newest">Newest first</option>
                  <option value="oldest">Oldest first</option>
                  <option value="project-asc">Project name A-Z</option>
                  <option value="project-desc">Project name Z-A</option>
                  <option value="customer-asc">Customer name A-Z</option>
                  <option value="customer-desc">Customer name Z-A</option>
                </select>
              </label>

              <button
                type="button"
                className="secondary-button refresh-button"
                onClick={refreshProjects}
                disabled={isLoading}
              >
                <Icon name="refresh" />
                Refresh
              </button>
            </div>
          </div>

          <div className="projects-table-wrap">
            <table className="projects-table">
              <thead>
                <tr>
                  <th>Project Name</th>
                  <th>Customer Name</th>
                  <th>Module Name</th>
                  <th>Author</th>
                  <th>Created On</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {displayedProjects.map((project) => (
                  <tr key={project.id}>
                    <td>
                      <Link href={`/projects/${project.id}`} className="project-name-link">
                        {getProjectName(project)}
                      </Link>
                    </td>
                    <td>{project.customer_name || "Not available"}</td>
                    <td>{project.module_name || "Not available"}</td>
                    <td>{project.name || "Not available"}</td>
                    <td>{formatProjectDate(project.created_at)}</td>
                    <td>
                      <div className="table-actions">
                        <Link href={`/projects/${project.id}`} className="secondary-button table-link">
                          Open
                        </Link>
                        <button
                          type="button"
                          className="danger-button table-delete"
                          disabled={deletingProjectId === project.id}
                          onClick={() => void handleDeleteProject(project)}
                        >
                          <Icon name="trash" />
                          {deletingProjectId === project.id ? "Deleting..." : "Delete"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {isLoading ? (
              <div className="empty-projects-state">
                <span className="empty-icon">
                  <Icon name="folder" />
                </span>
                <h3>Loading projects...</h3>
                <p>Please wait while the workspace refreshes.</p>
              </div>
            ) : null}

            {!isLoading && displayedProjects.length === 0 ? (
              <div className="empty-projects-state">
                <span className="empty-icon">
                  <Icon name="folder" />
                </span>
                <h3>{searchQuery.trim() ? "No matching projects" : "No projects found"}</h3>
                <p>
                  {searchQuery.trim()
                    ? "Try adjusting your search or sort criteria."
                    : "Create your first project to get started."}
                </p>
              </div>
            ) : null}
          </div>
        </section>
      </section>
    </main>
  );
}
