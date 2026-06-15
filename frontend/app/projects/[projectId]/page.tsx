"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChangeEvent, FormEvent, useEffect, useState } from "react";

import {
  formatProjectDate,
  createClassifyFilesJob,
  getProject,
  listExtractedContent,
  listProjectJobs,
  listProjectFiles,
  sourceRoleLabels,
  sourceRoles,
  uploadProjectFile,
  type ExtractedContent,
  type Job,
  type Project,
  type SourceRole,
  type UploadedFile,
} from "@/lib/projects";

const placeholderSections = [
  "AUD Plan",
  "Generated Documents",
];

type ExtractedContentMetadata = {
  paragraph_count?: number;
  table_count?: number;
  heading_count?: number;
  comment_count?: number;
};

type ExtractedContentJson = {
  source_role?: string | null;
  is_golden_source?: boolean;
  word_count?: number;
  character_count?: number;
  metadata?: ExtractedContentMetadata;
};

function parseExtractedContentJson(value: string | null): ExtractedContentJson {
  if (!value) {
    return {};
  }

  try {
    const parsed = JSON.parse(value) as unknown;

    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as ExtractedContentJson;
    }
  } catch {
    return {};
  }

  return {};
}

function formatSourceRole(value: string | null | undefined) {
  if (!value) {
    return "Not available";
  }

  if (value in sourceRoleLabels) {
    return sourceRoleLabels[value as SourceRole];
  }

  return value;
}

function buildCountSummary(jsonContent: ExtractedContentJson) {
  const counts: string[] = [];

  if (typeof jsonContent.word_count === "number") {
    counts.push(`${jsonContent.word_count} words`);
  }

  if (typeof jsonContent.metadata?.paragraph_count === "number") {
    counts.push(`${jsonContent.metadata.paragraph_count} paragraphs`);
  }

  if (typeof jsonContent.metadata?.table_count === "number") {
    counts.push(`${jsonContent.metadata.table_count} tables`);
  }

  return counts.length > 0 ? counts.join(" / ") : "Not available";
}

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [extractedContents, setExtractedContents] = useState<ExtractedContent[]>([]);
  const [sourceRole, setSourceRole] = useState<SourceRole>("unknown");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingFiles, setIsLoadingFiles] = useState(true);
  const [isLoadingJobs, setIsLoadingJobs] = useState(true);
  const [isLoadingExtractedContent, setIsLoadingExtractedContent] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isCreatingJob, setIsCreatingJob] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [fileMessage, setFileMessage] = useState<string | null>(null);
  const [jobMessage, setJobMessage] = useState<string | null>(null);
  const [extractedContentMessage, setExtractedContentMessage] = useState<string | null>(null);

  async function refreshFiles(projectId: string) {
    setIsLoadingFiles(true);
    setFileMessage(null);

    try {
      setUploadedFiles(await listProjectFiles(projectId));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setFileMessage(`Unable to load uploaded files: ${detail}`);
    } finally {
      setIsLoadingFiles(false);
    }
  }

  async function refreshJobs(projectId: string) {
    setIsLoadingJobs(true);
    setJobMessage(null);

    try {
      setJobs(await listProjectJobs(projectId));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setJobMessage(`Unable to load jobs: ${detail}`);
    } finally {
      setIsLoadingJobs(false);
    }
  }

  async function refreshExtractedContent(projectId: string) {
    setIsLoadingExtractedContent(true);
    setExtractedContentMessage(null);

    try {
      setExtractedContents(await listExtractedContent(projectId));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setExtractedContentMessage(`Unable to load extracted content: ${detail}`);
    } finally {
      setIsLoadingExtractedContent(false);
    }
  }

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
    void refreshFiles(params.projectId);
    void refreshJobs(params.projectId);
    void refreshExtractedContent(params.projectId);
  }, [params.projectId]);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile) {
      setFileMessage("Choose a file before uploading.");
      return;
    }

    setIsUploading(true);
    setFileMessage(null);

    try {
      await uploadProjectFile(params.projectId, sourceRole, selectedFile);
      setSelectedFile(null);
      setFileInputKey((current) => current + 1);
      await refreshFiles(params.projectId);
      setFileMessage("File uploaded.");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setFileMessage(`Unable to upload file: ${detail}`);
    } finally {
      setIsUploading(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] || null);
  }

  async function handleCreateClassifyJob() {
    setIsCreatingJob(true);
    setJobMessage(null);

    try {
      await createClassifyFilesJob(params.projectId);
      await refreshJobs(params.projectId);
      setJobMessage("Classify Files job created.");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setJobMessage(`Unable to create job: ${detail}`);
    } finally {
      setIsCreatingJob(false);
    }
  }

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

            <section className="panel" aria-labelledby="uploaded-files-title">
              <div className="section-heading">
                <h2 id="uploaded-files-title">Uploaded Files</h2>
              </div>

              <form className="upload-form" onSubmit={handleUpload}>
                <label>
                  <span>Source Role</span>
                  <select
                    value={sourceRole}
                    onChange={(event) => setSourceRole(event.target.value as SourceRole)}
                  >
                    {sourceRoles.map((role) => (
                      <option key={role} value={role}>
                        {sourceRoleLabels[role]}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  <span>File</span>
                  <input key={fileInputKey} type="file" onChange={handleFileChange} />
                </label>

                <div className="form-actions">
                  <button type="submit" className="primary-button" disabled={isUploading}>
                    {isUploading ? "Uploading..." : "Upload File"}
                  </button>
                </div>
              </form>

              {fileMessage ? <p className="status-message">{fileMessage}</p> : null}

              {isLoadingFiles ? <p className="muted-text">Loading uploaded files...</p> : null}

              {!isLoadingFiles && uploadedFiles.length === 0 ? (
                <p className="muted-text">No files uploaded yet.</p>
              ) : null}

              <div className="file-list">
                {uploadedFiles.map((uploadedFile) => (
                  <article key={uploadedFile.id} className="file-row">
                    <div>
                      <h3>{uploadedFile.original_filename}</h3>
                      <p>{uploadedFile.storage_path}</p>
                    </div>

                    <dl className="file-meta">
                      <div>
                        <dt>Source Role</dt>
                        <dd>
                          {uploadedFile.source_role
                            ? sourceRoleLabels[uploadedFile.source_role]
                            : sourceRoleLabels.unknown}
                        </dd>
                      </div>
                      <div>
                        <dt>File Type</dt>
                        <dd>{uploadedFile.file_type || "Not available"}</dd>
                      </div>
                      <div>
                        <dt>Created</dt>
                        <dd>{formatProjectDate(uploadedFile.created_at)}</dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
            </section>

            <section className="panel" aria-labelledby="jobs-title">
              <div className="section-heading">
                <div>
                  <h2 id="jobs-title">Jobs</h2>
                  <p className="muted-text">
                    Run the local backend worker manually to process pending jobs.
                  </p>
                </div>

                <div className="button-group">
                  <button
                    type="button"
                    className="primary-button"
                    onClick={handleCreateClassifyJob}
                    disabled={isCreatingJob}
                  >
                    {isCreatingJob ? "Creating..." : "Classify Files"}
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => refreshJobs(params.projectId)}
                    disabled={isLoadingJobs}
                  >
                    Refresh Jobs
                  </button>
                </div>
              </div>

              {jobMessage ? <p className="status-message">{jobMessage}</p> : null}

              {isLoadingJobs ? <p className="muted-text">Loading jobs...</p> : null}

              {!isLoadingJobs && jobs.length === 0 ? (
                <p className="muted-text">No jobs yet.</p>
              ) : null}

              <div className="job-list">
                {jobs.map((job) => (
                  <article key={job.id} className="job-row">
                    <div>
                      <h3>{job.job_type}</h3>
                      <p>{job.message || "No message"}</p>
                    </div>

                    <dl className="job-meta">
                      <div>
                        <dt>Status</dt>
                        <dd>{job.status}</dd>
                      </div>
                      <div>
                        <dt>Progress</dt>
                        <dd>{job.progress}%</dd>
                      </div>
                      <div>
                        <dt>Created</dt>
                        <dd>{formatProjectDate(job.created_at)}</dd>
                      </div>
                      <div>
                        <dt>Updated</dt>
                        <dd>{formatProjectDate(job.updated_at)}</dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
            </section>

            <section className="panel" aria-labelledby="extracted-content-title">
              <div className="section-heading">
                <div>
                  <h2 id="extracted-content-title">Extracted Content</h2>
                  <p className="muted-text">
                    Review extracted source records before AUD generation begins.
                  </p>
                </div>

                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => refreshExtractedContent(params.projectId)}
                  disabled={isLoadingExtractedContent}
                >
                  Refresh Extracted Content
                </button>
              </div>

              {extractedContentMessage ? (
                <p className="status-message">{extractedContentMessage}</p>
              ) : null}

              {isLoadingExtractedContent ? (
                <p className="muted-text">Loading extracted content...</p>
              ) : null}

              {!isLoadingExtractedContent && extractedContents.length === 0 ? (
                <p className="muted-text">No extracted content yet.</p>
              ) : null}

              <div className="extracted-content-list">
                {extractedContents.map((content) => {
                  const jsonContent = parseExtractedContentJson(content.json_content);

                  return (
                    <article key={content.id} className="extracted-content-row">
                      <div>
                        <h3>{content.title || "Untitled extracted content"}</h3>
                        <p>{content.content_type}</p>
                      </div>

                      <dl className="extracted-content-meta">
                        <div>
                          <dt>Created</dt>
                          <dd>{formatProjectDate(content.created_at)}</dd>
                        </div>
                        <div>
                          <dt>Source Role</dt>
                          <dd>{formatSourceRole(jsonContent.source_role)}</dd>
                        </div>
                        <div>
                          <dt>Golden Source</dt>
                          <dd>{jsonContent.is_golden_source ? "Yes" : "No"}</dd>
                        </div>
                        <div>
                          <dt>Counts</dt>
                          <dd>{buildCountSummary(jsonContent)}</dd>
                        </div>
                      </dl>

                      {content.text_content ? (
                        <details className="content-preview">
                          <summary>Preview</summary>
                          <pre>{content.text_content}</pre>
                        </details>
                      ) : null}
                    </article>
                  );
                })}
              </div>
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
