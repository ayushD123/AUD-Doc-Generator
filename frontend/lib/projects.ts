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
  | "aud_template"
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

export type GenerateDocxJobOptions = {
  use_ai_drafts?: boolean;
  include_draft_sections?: boolean;
  include_images?: boolean;
  include_open_points?: boolean;
};

export type AUDGenerationStart = {
  job_id: string;
  status: string;
  message: string;
};

export type AUDGenerationStatus = {
  job_id: string;
  status: string;
  current_stage: string | null;
  completed_stages: string[];
  failed_stage: string | null;
  warnings: string[];
  final_document_id: string | null;
  final_document_url: string | null;
  error: string | null;
};

export type ExtractedContent = {
  id: string;
  project_id: string;
  uploaded_file_id: string;
  content_type: string;
  title: string | null;
  text_content: string | null;
  json_content: string | null;
  created_at: string | null;
};

export type SourceFileReference = {
  uploaded_file_id: string;
  original_filename: string;
  source_role: string;
  file_type: string | null;
  extracted_content_ids: string[];
};

export type SourcePriorityItem = {
  source: string;
  priority: number;
  purpose: string;
  rule: string;
};

export type SourcePriorityReport = {
  has_explicit_template: boolean;
  golden_source_files: SourceFileReference[];
  source_roles_present: string[];
  priority_order: SourcePriorityItem[];
  warnings: string[];
  recommended_default_template_needed: boolean;
  notes: string[];
};

export type AUDPlan = {
  id: string;
  project_id: string;
  status: string;
  plan_json: string;
  created_at: string | null;
  updated_at: string | null;
};

export type AUDPlanSection = {
  section_id: string;
  title: string;
  source_file_ids: string[];
  source_content_ids: string[];
  source_role_basis: string;
  confidence: string;
  include_in_aud: boolean;
  notes: string[];
};

export type AUDPlanJson = {
  project_id?: string;
  status?: string;
  generation_basis?: string;
  default_template_required?: boolean;
  sections?: AUDPlanSection[];
  ai_enhanced_plan?: {
    sections?: AUDPlanSection[];
  };
};

export type OpenPoint = {
  id: string;
  project_id: string;
  topic: string;
  question: string;
  status: string;
  source_file_id: string | null;
  source_content_id: string | null;
  evidence: string | null;
  refinement_metadata?: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
};

export type GeneratedDocument = {
  id: string;
  project_id: string;
  filename: string;
  storage_path: string;
  document_type: string;
  created_at: string | null;
};

export type EvidenceItem = {
  id: string;
  project_id: string;
  source_uploaded_file_id: string | null;
  source_extracted_content_id: string | null;
  evidence_type: string;
  source_role: string | null;
  title: string | null;
  text: string | null;
  json_data: string | null;
  priority: number;
  confidence: string;
  created_at: string | null;
  updated_at: string | null;
};

export type SourceSummary = {
  id: string;
  project_id: string;
  source_uploaded_file_id: string | null;
  source_role: string;
  summary_type: string;
  summary_text: string;
  summary_json: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type AUDSectionDraft = {
  id: string;
  project_id: string;
  section_id: string;
  title: string;
  draft_text: string;
  draft_json: string | null;
  confidence: string;
  review_status: string;
  created_at: string | null;
  updated_at: string | null;
};

export const sourceRoles: SourceRole[] = [
  "aud_template",
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
  aud_template: "AUD Template",
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

export async function deleteProject(projectId: string) {
  const response = await fetch(`${getApiBaseUrl()}/projects/${projectId}`, {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(errorBody?.detail || `Request failed with HTTP ${response.status}.`);
  }
}

export function listProjectFiles(projectId: string) {
  return requestJson<UploadedFile[]>(`/projects/${projectId}/files`);
}

export async function deleteProjectFile(projectId: string, fileId: string) {
  const response = await fetch(`${getApiBaseUrl()}/projects/${projectId}/files/${fileId}`, {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(errorBody?.detail || `Request failed with HTTP ${response.status}.`);
  }
}

export function listProjectJobs(projectId: string) {
  return requestJson<Job[]>(`/projects/${projectId}/jobs`);
}

export function listExtractedContent(projectId: string) {
  return requestJson<ExtractedContent[]>(`/projects/${projectId}/extracted-content`);
}

export function getSourcePriorityReport(projectId: string) {
  return requestJson<SourcePriorityReport>(
    `/projects/${projectId}/source-priority-report`,
  );
}

export async function getAudPlan(projectId: string) {
  const response = await fetch(`${getApiBaseUrl()}/projects/${projectId}/aud-plan`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Request failed with HTTP ${response.status}.`);
  }

  return (await response.json()) as AUDPlan;
}

export function listOpenPoints(projectId: string) {
  return requestJson<OpenPoint[]>(`/projects/${projectId}/open-points`);
}

export function listGeneratedDocuments(projectId: string) {
  return requestJson<GeneratedDocument[]>(
    `/projects/${projectId}/generated-documents`,
  );
}

export function startAudGeneration(projectId: string) {
  return requestJson<AUDGenerationStart>(`/projects/${projectId}/generate-aud`, {
    method: "POST",
  });
}

export async function getAudGenerationStatus(projectId: string) {
  const response = await fetch(
    `${getApiBaseUrl()}/projects/${projectId}/generate-aud/status`,
    {
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Request failed with HTTP ${response.status}.`);
  }

  return (await response.json()) as AUDGenerationStatus;
}

export function listEvidenceItems(projectId: string) {
  return requestJson<EvidenceItem[]>(`/projects/${projectId}/evidence-items`);
}

export function listSourceSummaries(projectId: string) {
  return requestJson<SourceSummary[]>(`/projects/${projectId}/source-summaries`);
}

export function listSectionDrafts(projectId: string) {
  return requestJson<AUDSectionDraft[]>(`/projects/${projectId}/section-drafts`);
}

export function getGeneratedDocumentDownloadUrl(
  projectId: string,
  documentId: string,
) {
  return `${getApiBaseUrl()}/projects/${projectId}/generated-documents/${documentId}/download`;
}

export function createClassifyFilesJob(projectId: string) {
  return requestJson<Job>(`/projects/${projectId}/jobs/classify-files`, {
    method: "POST",
  });
}

export function createExtractAllJob(projectId: string) {
  return requestJson<Job>(`/projects/${projectId}/jobs/extract-all`, {
    method: "POST",
  });
}

export function createGenerateAudPlanJob(projectId: string) {
  return requestJson<Job>(`/projects/${projectId}/jobs/generate-aud-plan`, {
    method: "POST",
  });
}

export function createExtractOpenPointsJob(projectId: string) {
  return requestJson<Job>(`/projects/${projectId}/jobs/extract-open-points`, {
    method: "POST",
  });
}

export function createGenerateDocxJob(
  projectId: string,
  options?: GenerateDocxJobOptions,
) {
  return requestJson<Job>(`/projects/${projectId}/jobs/generate-docx`, {
    method: "POST",
    body: options ? JSON.stringify(options) : undefined,
  });
}

export function createBuildEvidenceIndexJob(projectId: string) {
  return requestJson<Job>(`/projects/${projectId}/jobs/build-evidence-index`, {
    method: "POST",
  });
}

export function createGenerateSourceSummariesAiJob(projectId: string) {
  return requestJson<Job>(
    `/projects/${projectId}/jobs/generate-source-summaries-ai`,
    {
      method: "POST",
    },
  );
}

export function createGenerateSectionDraftsAiJob(projectId: string) {
  return requestJson<Job>(
    `/projects/${projectId}/jobs/generate-section-drafts-ai`,
    {
      method: "POST",
    },
  );
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
