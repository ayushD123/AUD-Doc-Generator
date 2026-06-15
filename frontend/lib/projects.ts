export type Project = {
  id: string;
  name: string | null;
  email_id: string | null;
  customer_name: string | null;
  module_name: string | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
};

export type ProjectCreatePayload = {
  name?: string | null;
  email_id?: string | null;
  customer_name?: string | null;
  module_name?: string | null;
};

export type SourceRole =
  | "template_aud"
  | "final_aud_sample"
  | "fdd"
  | "kt_ppt"
  | "kt_session"
  | "kt_transcript"
  | "config_workbook"
  | "supporting_doc"
  | "unknown";

export type UploadedFile = {
  id: string;
  project_id: string;
  original_filename: string;
  file_type: string | null;
  storage_path: string;
  source_role: SourceRole | null;
  created_at: string | null;
};

export type Job = {
  id: string;
  project_id: string;
  job_type: string;
  status: string;
  progress: number;
  message: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export const sourceRoles: SourceRole[] = [
  "template_aud",
  "final_aud_sample",
  "fdd",
  "kt_ppt",
  "kt_session",
  "kt_transcript",
  "config_workbook",
  "supporting_doc",
  "unknown",
];

export const sourceRoleLabels: Record<SourceRole, string> = {
  template_aud: "Template AUD",
  final_aud_sample: "Final AUD Sample",
  fdd: "FDD - Functional Design Document",
  kt_ppt: "KT Presentation (PPTX)",
  kt_session: "KT Session (MP4)",
  kt_transcript: "KT Transcript",
  config_workbook: "Configuration Workbook",
  supporting_doc: "Supporting Document",
  unknown: "Other Files",
};

function getApiBaseUrl() {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!apiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured.");
  }

  return apiBaseUrl;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed with HTTP ${response.status}.`);
  }

  return (await response.json()) as T;
}

export function listProjects() {
  return requestJson<Project[]>("/projects");
}

export function getProject(projectId: string) {
  return requestJson<Project>(`/projects/${projectId}`);
}

export function createProject(payload: ProjectCreatePayload) {
  return requestJson<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listProjectFiles(projectId: string) {
  return requestJson<UploadedFile[]>(`/projects/${projectId}/files`);
}

export function listProjectJobs(projectId: string) {
  return requestJson<Job[]>(`/projects/${projectId}/jobs`);
}

export function createClassifyFilesJob(projectId: string) {
  return requestJson<Job>(`/projects/${projectId}/jobs/classify-files`, {
    method: "POST",
  });
}

export async function uploadProjectFile(
  projectId: string,
  sourceRole: SourceRole,
  file: File,
) {
  const formData = new FormData();
  formData.append("source_role", sourceRole);
  formData.append("file", file);

  const response = await fetch(`${getApiBaseUrl()}/projects/${projectId}/files`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(errorBody?.detail || `Request failed with HTTP ${response.status}.`);
  }

  return (await response.json()) as UploadedFile;
}

export function formatProjectDate(value: string | null) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
