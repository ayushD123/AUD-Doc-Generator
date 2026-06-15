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

export function formatProjectDate(value: string | null) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
