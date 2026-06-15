"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChangeEvent, FormEvent, useEffect, useState } from "react";

import {
  formatProjectDate,
  getProject,
  listProjectFiles,
  sourceRoleLabels,
  sourceRoles,
  uploadProjectFile,
  type Project,
  type SourceRole,
  type UploadedFile,
} from "@/lib/projects";

const placeholderSections = [
  "Jobs",
  "AUD Plan",
  "Generated Documents",
];

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [sourceRole, setSourceRole] = useState<SourceRole>("unknown");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingFiles, setIsLoadingFiles] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [fileMessage, setFileMessage] = useState<string | null>(null);

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
