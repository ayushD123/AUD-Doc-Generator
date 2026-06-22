"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

import {
  formatProjectDate,
  createBuildEvidenceIndexJob,
  createClassifyFilesJob,
  createExtractOpenPointsJob,
  createExtractAllJob,
  createGenerateSourceSummariesAiJob,
  createGenerateSectionDraftsAiJob,
  createGenerateAudPlanJob,
  createGenerateDocxJob,
  deleteProjectFile,
  getAudGenerationStatus,
  getAudPlan,
  getGeneratedDocumentDownloadUrl,
  getProject,
  getSourcePriorityReport,
  listExtractedContent,
  listEvidenceItems,
  listGeneratedDocuments,
  listOpenPoints,
  listProjectJobs,
  listProjectFiles,
  listSourceSummaries,
  listSectionDrafts,
  sourceRoleLabels,
  sourceRoles,
  startAudGeneration,
  uploadProjectFile,
  type AUDGenerationStatus,
  type AUDPlan,
  type AUDPlanJson,
  type AUDSectionDraft,
  type EvidenceItem,
  type ExtractedContent,
  type GeneratedDocument,
  type Job,
  type OpenPoint,
  type Project,
  type SourceRole,
  type SourcePriorityReport,
  type SourceSummary,
  type UploadedFile,
} from "@/lib/projects";

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

type SourceSummaryJson = {
  source_role?: string;
  summary?: string;
  important_topics?: string[];
  tables_or_configurations?: string[];
  processes?: string[];
  screenshots_or_images_to_consider?: string[];
  open_or_unresolved_items?: string[];
  source_confidence?: string;
  aud_usage_guidance?: string;
};

type SectionDraftJson = {
  used_evidence_item_ids?: string[];
  included_tables?: unknown[];
  included_images?: unknown[];
  unsupported_details?: unknown[];
  open_point_candidates?: unknown[];
  placeholders?: unknown[];
};

type UploadedFileListItem = UploadedFile & {
  uploadStatus?: "pending";
};

const pendingUploadIdPrefix = "pending-upload-";

function getClientFileType(filename: string) {
  const extension = filename.split(".").pop();
  return extension && extension !== filename ? extension.toLowerCase() : null;
}

function buildPendingUploadedFile(
  projectId: string,
  sourceRole: SourceRole,
  file: File,
): UploadedFileListItem {
  return {
    id: `${pendingUploadIdPrefix}${crypto.randomUUID()}`,
    project_id: projectId,
    original_filename: file.name || "uploaded_file",
    file_type: getClientFileType(file.name),
    storage_path: "",
    source_role: sourceRole,
    created_at: new Date().toISOString(),
    uploadStatus: "pending",
  };
}

function isPendingUploadedFile(uploadedFile: UploadedFileListItem) {
  return uploadedFile.uploadStatus === "pending";
}

function waitForNextPaint() {
  return new Promise<void>((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve());
    });
  });
}

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

function parseAudPlanJson(value: string | null): AUDPlanJson {
  if (!value) {
    return {};
  }

  try {
    const parsed = JSON.parse(value) as unknown;

    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as AUDPlanJson;
    }
  } catch {
    return {};
  }

  return {};
}

function parseSourceSummaryJson(value: string | null): SourceSummaryJson {
  if (!value) {
    return {};
  }

  try {
    const parsed = JSON.parse(value) as unknown;

    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as SourceSummaryJson;
    }
  } catch {
    return {};
  }

  return {};
}

function parseSectionDraftJson(value: string | null): SectionDraftJson {
  if (!value) {
    return {};
  }

  try {
    const parsed = JSON.parse(value) as unknown;

    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as SectionDraftJson;
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

function formatPrioritySource(value: string) {
  if (value === "default_scm_template") {
    return "Default SCM Template";
  }

  if (value === "aud_template") {
    return "AUD Template";
  }

  return formatSourceRole(value);
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

function buildEvidencePreview(value: string | null) {
  if (!value) {
    return "Not available";
  }

  const normalizedValue = value.trim().replace(/\s+/g, " ");
  return normalizedValue.length > 180
    ? `${normalizedValue.slice(0, 180).trim()}...`
    : normalizedValue;
}

type EvidenceGroupCount = {
  evidenceType: string;
  sourceRole: string | null;
  count: number;
};

function buildEvidenceGroupCounts(items: EvidenceItem[]): EvidenceGroupCount[] {
  const counts = new Map<string, EvidenceGroupCount>();

  for (const item of items) {
    const sourceRole = item.source_role || null;
    const key = `${item.evidence_type}::${sourceRole || "unknown"}`;
    const current = counts.get(key);

    if (current) {
      current.count += 1;
    } else {
      counts.set(key, {
        evidenceType: item.evidence_type,
        sourceRole,
        count: 1,
      });
    }
  }

  return Array.from(counts.values()).sort((left, right) => {
    if (right.count !== left.count) {
      return right.count - left.count;
    }

    if (left.evidenceType !== right.evidenceType) {
      return left.evidenceType.localeCompare(right.evidenceType);
    }

    return (left.sourceRole || "").localeCompare(right.sourceRole || "");
  });
}

function buildSourceSummaryGroups(items: SourceSummary[]) {
  const groups = new Map<string, SourceSummary[]>();

  for (const item of items) {
    groups.set(item.source_role, [...(groups.get(item.source_role) ?? []), item]);
  }

  return Array.from(groups.entries()).sort(([left], [right]) =>
    left.localeCompare(right),
  );
}

function formatSummaryList(values: string[] | undefined) {
  if (!values || values.length === 0) {
    return "Not available";
  }

  return values.join(", ");
}

function formatDraftDetail(value: unknown) {
  if (typeof value === "string") {
    return value;
  }

  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    const question = record.question || record.text;
    const topic = record.topic;

    if (typeof question === "string" && typeof topic === "string") {
      return `${topic}: ${question}`;
    }

    if (typeof question === "string") {
      return question;
    }

    return JSON.stringify(value);
  }

  return String(value ?? "");
}

function buildDraftPreview(value: string) {
  const normalizedValue = value.trim().replace(/\s+/g, " ");
  return normalizedValue.length > 260
    ? `${normalizedValue.slice(0, 260).trim()}...`
    : normalizedValue || "Not available";
}

function getAudSectionOrder(audPlanJson: AUDPlanJson) {
  const enhancedSections = audPlanJson.ai_enhanced_plan?.sections;
  const sections =
    enhancedSections && enhancedSections.length > 0
      ? enhancedSections
      : audPlanJson.sections ?? [];

  return sections.filter((section) => section.include_in_aud !== false);
}

function buildOrderedSectionDrafts(
  drafts: AUDSectionDraft[],
  audPlanJson: AUDPlanJson,
) {
  const draftsBySectionId = new Map<string, AUDSectionDraft[]>();

  for (const draft of drafts) {
    draftsBySectionId.set(draft.section_id, [
      ...(draftsBySectionId.get(draft.section_id) ?? []),
      draft,
    ]);
  }

  const ordered = getAudSectionOrder(audPlanJson).map((section, index) => {
    const sectionDrafts = draftsBySectionId.get(section.section_id) ?? [];
    draftsBySectionId.delete(section.section_id);

    return {
      order: index + 1,
      sectionId: section.section_id,
      title: section.title,
      drafts: sectionDrafts,
    };
  });

  const unmappedDrafts = Array.from(draftsBySectionId.values()).flat();

  if (unmappedDrafts.length > 0) {
    ordered.push({
      order: ordered.length + 1,
      sectionId: "unmapped-section-drafts",
      title: "Unmapped Section Drafts",
      drafts: unmappedDrafts,
    });
  }

  return ordered.filter((group) => group.drafts.length > 0);
}

function isAudGenerationTerminal(status: string | null | undefined) {
  return (
    status === "completed" ||
    status === "completed_with_warnings" ||
    status === "failed"
  );
}

function isAudGenerationSuccess(status: string | null | undefined) {
  return status === "completed" || status === "completed_with_warnings";
}

function formatStageLabel(value: string | null | undefined) {
  if (!value) {
    return "Not started";
  }

  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const uploadInFlightRef = useRef(false);
  const handledTerminalGenerationRef = useRef<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [pendingUploadedFiles, setPendingUploadedFiles] = useState<
    UploadedFileListItem[]
  >([]);
  const [deletingUploadedFileIds, setDeletingUploadedFileIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [jobs, setJobs] = useState<Job[]>([]);
  const [extractedContents, setExtractedContents] = useState<ExtractedContent[]>([]);
  const [evidenceItems, setEvidenceItems] = useState<EvidenceItem[]>([]);
  const [sourceSummaries, setSourceSummaries] = useState<SourceSummary[]>([]);
  const [sectionDrafts, setSectionDrafts] = useState<AUDSectionDraft[]>([]);
  const [openPoints, setOpenPoints] = useState<OpenPoint[]>([]);
  const [generatedDocuments, setGeneratedDocuments] = useState<GeneratedDocument[]>([]);
  const [audGenerationStatus, setAudGenerationStatus] =
    useState<AUDGenerationStatus | null>(null);
  const [audPlan, setAudPlan] = useState<AUDPlan | null>(null);
  const [sourcePriorityReport, setSourcePriorityReport] =
    useState<SourcePriorityReport | null>(null);
  const [sourceRole, setSourceRole] = useState<SourceRole>("unknown");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingFiles, setIsLoadingFiles] = useState(true);
  const [isLoadingJobs, setIsLoadingJobs] = useState(true);
  const [isLoadingExtractedContent, setIsLoadingExtractedContent] = useState(true);
  const [isLoadingEvidenceItems, setIsLoadingEvidenceItems] = useState(true);
  const [isLoadingSourceSummaries, setIsLoadingSourceSummaries] = useState(true);
  const [isLoadingSectionDrafts, setIsLoadingSectionDrafts] = useState(true);
  const [isLoadingOpenPoints, setIsLoadingOpenPoints] = useState(true);
  const [isLoadingGeneratedDocuments, setIsLoadingGeneratedDocuments] = useState(true);
  const [isLoadingAudGenerationStatus, setIsLoadingAudGenerationStatus] =
    useState(true);
  const [isLoadingAudPlan, setIsLoadingAudPlan] = useState(true);
  const [isLoadingSourcePriority, setIsLoadingSourcePriority] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isCreatingJob, setIsCreatingJob] = useState(false);
  const [isCreatingExtractAllJob, setIsCreatingExtractAllJob] = useState(false);
  const [isCreatingAudPlanJob, setIsCreatingAudPlanJob] = useState(false);
  const [isCreatingOpenPointsJob, setIsCreatingOpenPointsJob] = useState(false);
  const [isCreatingDocxJob, setIsCreatingDocxJob] = useState(false);
  const [isCreatingEvidenceIndexJob, setIsCreatingEvidenceIndexJob] = useState(false);
  const [isCreatingSourceSummariesJob, setIsCreatingSourceSummariesJob] =
    useState(false);
  const [isCreatingSectionDraftsJob, setIsCreatingSectionDraftsJob] =
    useState(false);
  const [isStartingAudGeneration, setIsStartingAudGeneration] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>(
    {},
  );
  const [message, setMessage] = useState<string | null>(null);
  const [fileMessage, setFileMessage] = useState<string | null>(null);
  const [jobMessage, setJobMessage] = useState<string | null>(null);
  const [extractedContentMessage, setExtractedContentMessage] = useState<string | null>(
    null,
  );
  const [evidenceItemsMessage, setEvidenceItemsMessage] = useState<string | null>(
    null,
  );
  const [sourceSummariesMessage, setSourceSummariesMessage] = useState<string | null>(
    null,
  );
  const [sectionDraftsMessage, setSectionDraftsMessage] = useState<string | null>(
    null,
  );
  const [openPointsMessage, setOpenPointsMessage] = useState<string | null>(null);
  const [generatedDocumentsMessage, setGeneratedDocumentsMessage] = useState<
    string | null
  >(null);
  const [audGenerationMessage, setAudGenerationMessage] = useState<string | null>(
    null,
  );
  const [audPlanMessage, setAudPlanMessage] = useState<string | null>(null);
  const [sourcePriorityMessage, setSourcePriorityMessage] = useState<string | null>(
    null,
  );

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

  async function refreshEvidenceItems(projectId: string) {
    setIsLoadingEvidenceItems(true);
    setEvidenceItemsMessage(null);

    try {
      setEvidenceItems(await listEvidenceItems(projectId));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setEvidenceItemsMessage(`Unable to load evidence items: ${detail}`);
    } finally {
      setIsLoadingEvidenceItems(false);
    }
  }

  async function refreshSourceSummaries(projectId: string) {
    setIsLoadingSourceSummaries(true);
    setSourceSummariesMessage(null);

    try {
      setSourceSummaries(await listSourceSummaries(projectId));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setSourceSummariesMessage(`Unable to load source summaries: ${detail}`);
    } finally {
      setIsLoadingSourceSummaries(false);
    }
  }

  async function refreshSectionDrafts(projectId: string) {
    setIsLoadingSectionDrafts(true);
    setSectionDraftsMessage(null);

    try {
      setSectionDrafts(await listSectionDrafts(projectId));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setSectionDraftsMessage(`Unable to load section drafts: ${detail}`);
    } finally {
      setIsLoadingSectionDrafts(false);
    }
  }

  async function refreshOpenPoints(projectId: string) {
    setIsLoadingOpenPoints(true);
    setOpenPointsMessage(null);

    try {
      setOpenPoints(await listOpenPoints(projectId));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setOpenPointsMessage(`Unable to load open points: ${detail}`);
    } finally {
      setIsLoadingOpenPoints(false);
    }
  }

  async function refreshGeneratedDocuments(projectId: string) {
    setIsLoadingGeneratedDocuments(true);
    setGeneratedDocumentsMessage(null);

    try {
      setGeneratedDocuments(await listGeneratedDocuments(projectId));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setGeneratedDocumentsMessage(`Unable to load generated documents: ${detail}`);
    } finally {
      setIsLoadingGeneratedDocuments(false);
    }
  }

  async function refreshAudGenerationStatus(projectId: string) {
    setIsLoadingAudGenerationStatus(true);

    try {
      setAudGenerationStatus(await getAudGenerationStatus(projectId));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setAudGenerationMessage(`Unable to load AUD generation status: ${detail}`);
    } finally {
      setIsLoadingAudGenerationStatus(false);
    }
  }

  async function refreshAudPlan(projectId: string) {
    setIsLoadingAudPlan(true);
    setAudPlanMessage(null);

    try {
      setAudPlan(await getAudPlan(projectId));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setAudPlanMessage(`Unable to load AUD plan: ${detail}`);
    } finally {
      setIsLoadingAudPlan(false);
    }
  }

  async function refreshSourcePriority(projectId: string) {
    setIsLoadingSourcePriority(true);
    setSourcePriorityMessage(null);

    try {
      setSourcePriorityReport(await getSourcePriorityReport(projectId));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setSourcePriorityMessage(`Unable to load source priority: ${detail}`);
    } finally {
      setIsLoadingSourcePriority(false);
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
    void refreshEvidenceItems(params.projectId);
    void refreshSourceSummaries(params.projectId);
    void refreshSectionDrafts(params.projectId);
    void refreshOpenPoints(params.projectId);
    void refreshGeneratedDocuments(params.projectId);
    void refreshAudGenerationStatus(params.projectId);
    void refreshAudPlan(params.projectId);
    void refreshSourcePriority(params.projectId);
  }, [params.projectId]);

  useEffect(() => {
    if (
      !audGenerationStatus ||
      isAudGenerationTerminal(audGenerationStatus.status)
    ) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshAudGenerationStatus(params.projectId);
    }, 4000);

    return () => window.clearInterval(intervalId);
  }, [audGenerationStatus?.job_id, audGenerationStatus?.status, params.projectId]);

  useEffect(() => {
    if (!audGenerationStatus || !isAudGenerationTerminal(audGenerationStatus.status)) {
      return;
    }

    const handledKey = `${audGenerationStatus.job_id}:${audGenerationStatus.status}`;
    if (handledTerminalGenerationRef.current === handledKey) {
      return;
    }

    handledTerminalGenerationRef.current = handledKey;

    if (isAudGenerationSuccess(audGenerationStatus.status)) {
      setAudGenerationMessage("Final AUD is ready");
      void Promise.all([
        refreshGeneratedDocuments(params.projectId),
        refreshJobs(params.projectId),
        refreshAudPlan(params.projectId),
        refreshOpenPoints(params.projectId),
        refreshEvidenceItems(params.projectId),
        refreshSourceSummaries(params.projectId),
        refreshSectionDrafts(params.projectId),
      ]);
    } else if (audGenerationStatus.status === "failed") {
      setAudGenerationMessage("AUD generation failed.");
      void refreshJobs(params.projectId);
    }
  }, [audGenerationStatus, params.projectId]);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (uploadInFlightRef.current) {
      setFileMessage("Upload already in progress.");
      return;
    }

    if (!selectedFile) {
      setFileMessage("Choose a file before uploading.");
      return;
    }

    uploadInFlightRef.current = true;
    setIsUploading(true);
    setFileMessage(null);

    const fileToUpload = selectedFile;
    const sourceRoleToUpload = sourceRole;
    const pendingUploadedFile = buildPendingUploadedFile(
      params.projectId,
      sourceRoleToUpload,
      fileToUpload,
    );

    setPendingUploadedFiles((current) => [pendingUploadedFile, ...current]);
    setSelectedFile(null);
    setFileInputKey((current) => current + 1);
    await waitForNextPaint();

    try {
      const uploadedFile = await uploadProjectFile(
        params.projectId,
        sourceRoleToUpload,
        fileToUpload,
      );
      setPendingUploadedFiles((current) =>
        current.filter((item) => item.id !== pendingUploadedFile.id),
      );
      setUploadedFiles((current) => [
        uploadedFile,
        ...current.filter((item) => item.id !== uploadedFile.id),
      ]);
      void refreshFiles(params.projectId);
      void refreshSourcePriority(params.projectId);
      setFileMessage("File uploaded.");
    } catch (error) {
      setPendingUploadedFiles((current) =>
        current.filter((item) => item.id !== pendingUploadedFile.id),
      );
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setFileMessage(`Unable to upload file: ${detail}`);
    } finally {
      uploadInFlightRef.current = false;
      setIsUploading(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] || null);
  }

  async function handleDeleteUploadedFile(uploadedFile: UploadedFileListItem) {
    if (isPendingUploadedFile(uploadedFile)) {
      return;
    }

    const confirmed = window.confirm(
      `Remove ${uploadedFile.original_filename} from this project?`,
    );

    if (!confirmed) {
      return;
    }

    setDeletingUploadedFileIds((current) => new Set(current).add(uploadedFile.id));
    setFileMessage(null);

    try {
      await deleteProjectFile(params.projectId, uploadedFile.id);
      setUploadedFiles((current) =>
        current.filter((item) => item.id !== uploadedFile.id),
      );
      void Promise.all([
        refreshSourcePriority(params.projectId),
        refreshExtractedContent(params.projectId),
        refreshEvidenceItems(params.projectId),
        refreshSourceSummaries(params.projectId),
        refreshOpenPoints(params.projectId),
      ]);
      setFileMessage("File removed.");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setFileMessage(`Unable to remove file: ${detail}`);
    } finally {
      setDeletingUploadedFileIds((current) => {
        const next = new Set(current);
        next.delete(uploadedFile.id);
        return next;
      });
    }
  }

  async function handleGenerateAud() {
    setIsStartingAudGeneration(true);
    setAudGenerationMessage(null);
    handledTerminalGenerationRef.current = null;

    try {
      const generationStart = await startAudGeneration(params.projectId);
      setAudGenerationStatus({
        job_id: generationStart.job_id,
        status: generationStart.status,
        current_stage: null,
        completed_stages: [],
        failed_stage: null,
        warnings: [],
        final_document_id: null,
        final_document_url: null,
        error: null,
      });
      setAudGenerationMessage(generationStart.message);
      await Promise.all([
        refreshAudGenerationStatus(params.projectId),
        refreshJobs(params.projectId),
      ]);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setAudGenerationMessage(`Unable to start AUD generation: ${detail}`);
    } finally {
      setIsStartingAudGeneration(false);
    }
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

  async function handleCreateExtractAllJob() {
    setIsCreatingExtractAllJob(true);
    setJobMessage(null);

    try {
      await createExtractAllJob(params.projectId);
      await refreshJobs(params.projectId);
      setJobMessage("Extract All Files job created.");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setJobMessage(`Unable to create job: ${detail}`);
    } finally {
      setIsCreatingExtractAllJob(false);
    }
  }

  async function handleCreateAudPlanJob() {
    setIsCreatingAudPlanJob(true);
    setJobMessage(null);

    try {
      await createGenerateAudPlanJob(params.projectId);
      await refreshJobs(params.projectId);
      setJobMessage("Generate AUD Plan job created.");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setJobMessage(`Unable to create job: ${detail}`);
    } finally {
      setIsCreatingAudPlanJob(false);
    }
  }

  async function handleCreateOpenPointsJob() {
    setIsCreatingOpenPointsJob(true);
    setJobMessage(null);

    try {
      await createExtractOpenPointsJob(params.projectId);
      await refreshJobs(params.projectId);
      setJobMessage("Extract Open Points job created.");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setJobMessage(`Unable to create job: ${detail}`);
    } finally {
      setIsCreatingOpenPointsJob(false);
    }
  }

  async function handleCreateDocxJob() {
    setIsCreatingDocxJob(true);
    setGeneratedDocumentsMessage(null);

    try {
      await createGenerateDocxJob(params.projectId);
      await refreshJobs(params.projectId);
      setGeneratedDocumentsMessage(
        "Generate DOCX job created. Run the local worker, then refresh generated documents.",
      );
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setGeneratedDocumentsMessage(`Unable to create DOCX generation job: ${detail}`);
    } finally {
      setIsCreatingDocxJob(false);
    }
  }

  async function handleCreateEvidenceIndexJob() {
    setIsCreatingEvidenceIndexJob(true);
    setEvidenceItemsMessage(null);

    try {
      await createBuildEvidenceIndexJob(params.projectId);
      await refreshJobs(params.projectId);
      setEvidenceItemsMessage(
        "Evidence index build job created. Refresh Evidence after worker processing completes.",
      );
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setEvidenceItemsMessage(`Unable to create evidence index job: ${detail}`);
    } finally {
      setIsCreatingEvidenceIndexJob(false);
    }
  }

  async function handleCreateSourceSummariesJob() {
    setIsCreatingSourceSummariesJob(true);
    setSourceSummariesMessage(null);

    try {
      await createGenerateSourceSummariesAiJob(params.projectId);
      await refreshJobs(params.projectId);
      setSourceSummariesMessage(
        "AI source summary job created. Refresh Source Summaries after worker processing completes.",
      );
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setSourceSummariesMessage(
        `Unable to create AI source summary job: ${detail}`,
      );
    } finally {
      setIsCreatingSourceSummariesJob(false);
    }
  }

  async function handleCreateSectionDraftsJob() {
    setIsCreatingSectionDraftsJob(true);
    setSectionDraftsMessage(null);

    try {
      await createGenerateSectionDraftsAiJob(params.projectId);
      await refreshJobs(params.projectId);
      setSectionDraftsMessage(
        "AI section draft job created. Refresh Section Drafts after worker processing completes.",
      );
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setSectionDraftsMessage(
        `Unable to create AI section draft job: ${detail}`,
      );
    } finally {
      setIsCreatingSectionDraftsJob(false);
    }
  }

  function isSectionExpanded(sectionKey: string) {
    return expandedSections[sectionKey] ?? false;
  }

  function toggleSection(sectionKey: string) {
    setExpandedSections((current) => ({
      ...current,
      [sectionKey]: !(current[sectionKey] ?? false),
    }));
  }

  const audPlanJson = parseAudPlanJson(audPlan?.plan_json ?? null);
  const plannedSections = audPlanJson.sections ?? [];
  const orderedSectionDraftGroups = buildOrderedSectionDrafts(
    sectionDrafts,
    audPlanJson,
  );
  const visibleUploadedFiles: UploadedFileListItem[] = [
    ...pendingUploadedFiles,
    ...uploadedFiles,
  ];
  const evidenceGroupCounts = buildEvidenceGroupCounts(evidenceItems);
  const sourceSummaryGroups = buildSourceSummaryGroups(sourceSummaries);
  const isAudGenerationRunning =
    !!audGenerationStatus && !isAudGenerationTerminal(audGenerationStatus.status);
  const isGenerateAudDisabled = isStartingAudGeneration || isAudGenerationRunning;
  const orderedGeneratedDocuments = [...generatedDocuments].sort((left, right) => {
    const finalDocumentId = audGenerationStatus?.final_document_id;

    if (finalDocumentId) {
      if (left.id === finalDocumentId) {
        return -1;
      }

      if (right.id === finalDocumentId) {
        return 1;
      }
    }

    return (right.created_at || "").localeCompare(left.created_at || "");
  });
  const finalGeneratedDocument =
    (audGenerationStatus?.final_document_id
      ? orderedGeneratedDocuments.find(
          (document) => document.id === audGenerationStatus.final_document_id,
        )
      : null) ??
    orderedGeneratedDocuments.find(
      (document) => document.document_type === "aud_docx",
    ) ??
    orderedGeneratedDocuments[0] ??
    null;
  const topEvidenceItems = [...evidenceItems]
    .sort((left, right) => {
      if (right.priority !== left.priority) {
        return right.priority - left.priority;
      }

      return (left.created_at || "").localeCompare(right.created_at || "");
    })
    .slice(0, 10);
  const renderSectionToggle = (sectionKey: string) => (
    <button
      type="button"
      className="secondary-button section-toggle-button"
      onClick={() => toggleSection(sectionKey)}
      aria-expanded={isSectionExpanded(sectionKey)}
    >
      {isSectionExpanded(sectionKey) ? "Collapse" : "Expand"}
    </button>
  );

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

            <section className="panel final-aud-panel" aria-labelledby="final-aud-title">
              <div className="section-heading">
                <div>
                  <h2 id="final-aud-title">Final Generated AUD DOCX</h2>
                  <p className="muted-text">Download the latest generated AUD document.</p>
                </div>
              </div>

              <div className="panel-content">
                {isAudGenerationSuccess(audGenerationStatus?.status) ? (
                  <p className="status-message status-success">Final AUD is ready</p>
                ) : null}

                {isLoadingGeneratedDocuments ? (
                  <p className="muted-text">Loading generated documents...</p>
                ) : null}

                {!isLoadingGeneratedDocuments && finalGeneratedDocument ? (
                  <article className="generated-document-row final-document-row">
                    <div>
                      <h3>{finalGeneratedDocument.filename}</h3>
                      <p>{finalGeneratedDocument.document_type}</p>
                    </div>

                    <dl className="generated-document-meta">
                      <div>
                        <dt>Created</dt>
                        <dd>{formatProjectDate(finalGeneratedDocument.created_at)}</dd>
                      </div>
                      <div>
                        <dt>Download</dt>
                        <dd>
                          <a
                            className="download-link"
                            href={getGeneratedDocumentDownloadUrl(
                              params.projectId,
                              finalGeneratedDocument.id,
                            )}
                          >
                            Download DOCX
                          </a>
                        </dd>
                      </div>
                    </dl>
                  </article>
                ) : null}

                {!isLoadingGeneratedDocuments && !finalGeneratedDocument ? (
                  <p className="muted-text">No final AUD generated yet.</p>
                ) : null}
              </div>
            </section>

            <section className="panel" aria-labelledby="aud-generation-title">
              <div className="section-heading">
                <div>
                  <h2 id="aud-generation-title">AUD Generation</h2>
                  <p className="muted-text">
                    Start the end-to-end AUD pipeline after project files are uploaded.
                  </p>
                </div>

                <button
                  type="button"
                  className="primary-button generate-aud-button"
                  onClick={handleGenerateAud}
                  disabled={isGenerateAudDisabled}
                >
                  {isGenerateAudDisabled ? "Generating..." : "Generate AUD"}
                </button>
              </div>

              <div className="panel-content">
                {audGenerationMessage ? (
                  <p
                    className={
                      audGenerationStatus?.status === "failed"
                        ? "status-message status-error"
                        : "status-message"
                    }
                  >
                    {audGenerationMessage}
                  </p>
                ) : null}

                {isLoadingAudGenerationStatus ? (
                  <p className="muted-text">Loading AUD generation status...</p>
                ) : null}

                {!isLoadingAudGenerationStatus && !audGenerationStatus ? (
                  <p className="muted-text">AUD generation has not started yet.</p>
                ) : null}

                {audGenerationStatus ? (
                  <div className="generation-status-card">
                    <dl className="generation-status-grid">
                      <div>
                        <dt>Status</dt>
                        <dd>{audGenerationStatus.status}</dd>
                      </div>
                      <div>
                        <dt>Current Stage</dt>
                        <dd>{formatStageLabel(audGenerationStatus.current_stage)}</dd>
                      </div>
                      <div>
                        <dt>Failed Stage</dt>
                        <dd>{formatStageLabel(audGenerationStatus.failed_stage)}</dd>
                      </div>
                    </dl>

                    <div className="generation-status-block">
                      <h3>Completed Stages</h3>
                      {audGenerationStatus.completed_stages.length > 0 ? (
                        <ol className="stage-list">
                          {audGenerationStatus.completed_stages.map((stage) => (
                            <li key={stage}>{formatStageLabel(stage)}</li>
                          ))}
                        </ol>
                      ) : (
                        <p className="muted-text">No stages completed yet.</p>
                      )}
                    </div>

                    <div className="generation-status-block">
                      <h3>Warnings</h3>
                      {audGenerationStatus.warnings.length > 0 ? (
                        <ul className="warning-list">
                          {audGenerationStatus.warnings.map((warning) => (
                            <li key={warning}>{warning}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="muted-text">No warnings.</p>
                      )}
                    </div>

                    {audGenerationStatus.status === "failed" ? (
                      <div className="generation-status-block">
                        <h3>Error</h3>
                        <p className="status-message status-error">
                          {audGenerationStatus.error || "Unknown backend error."}
                        </p>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </section>

            <section className="panel" aria-labelledby="metadata-title">
              <div className="section-heading">
                <h2 id="metadata-title">Project Metadata</h2>
                {renderSectionToggle("metadata")}
              </div>

              {isSectionExpanded("metadata") ? (
                <div className="panel-content">
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
                </div>
              ) : null}
            </section>

            <section className="panel" aria-labelledby="uploaded-files-title">
              <div className="section-heading">
                <h2 id="uploaded-files-title">Uploaded Files</h2>
                {renderSectionToggle("uploaded-files")}
              </div>

              {isSectionExpanded("uploaded-files") ? (
                <div className="panel-content">
                  <form className="upload-form" onSubmit={handleUpload}>
                    <label>
                      <span>Source Role</span>
                      <select
                        value={sourceRole}
                        disabled={isUploading}
                        onChange={(event) =>
                          setSourceRole(event.target.value as SourceRole)
                        }
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
                      <input
                        key={fileInputKey}
                        type="file"
                        disabled={isUploading}
                        onChange={handleFileChange}
                      />
                    </label>

                    <div className="form-actions">
                      <button
                        type="submit"
                        className="primary-button"
                        disabled={isUploading || !selectedFile}
                      >
                        {isUploading ? "Uploading..." : "Upload File"}
                      </button>
                    </div>
                  </form>

                  {fileMessage ? <p className="status-message">{fileMessage}</p> : null}

                  {isLoadingFiles ? (
                    <p className="muted-text">Loading uploaded files...</p>
                  ) : null}

                  {!isLoadingFiles && visibleUploadedFiles.length === 0 ? (
                    <p className="muted-text">No files uploaded yet.</p>
                  ) : null}

                  <div className="file-list">
                    {visibleUploadedFiles.map((uploadedFile) => (
                      <article key={uploadedFile.id} className="file-row">
                        <div>
                          <h3>{uploadedFile.original_filename}</h3>
                          <p>
                            {isPendingUploadedFile(uploadedFile)
                              ? "Upload in progress..."
                              : uploadedFile.storage_path}
                          </p>
                          {!isPendingUploadedFile(uploadedFile) ? (
                            <button
                              type="button"
                              className="secondary-button file-remove-button"
                              disabled={deletingUploadedFileIds.has(uploadedFile.id)}
                              onClick={() => void handleDeleteUploadedFile(uploadedFile)}
                            >
                              {deletingUploadedFileIds.has(uploadedFile.id)
                                ? "Removing..."
                                : "Remove"}
                            </button>
                          ) : null}
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
                </div>
              ) : null}
            </section>

            <section className="panel" aria-labelledby="jobs-title">
              <div className="section-heading">
                <div>
                  <h2 id="jobs-title">Jobs / Debug Information</h2>
                  <p className="muted-text">
                    Inspect backend job history and developer-only pipeline controls.
                  </p>
                </div>

                {renderSectionToggle("jobs")}
              </div>

              {isSectionExpanded("jobs") ? (
                <div className="panel-content">
                  <details className="debug-actions">
                    <summary>Developer / Debug Actions</summary>
                    <div className="button-group section-actions">
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handleCreateClassifyJob}
                        disabled={isCreatingJob}
                      >
                        {isCreatingJob ? "Creating..." : "Classify Files"}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handleCreateExtractAllJob}
                        disabled={isCreatingExtractAllJob}
                      >
                        {isCreatingExtractAllJob ? "Creating..." : "Extract All Files"}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handleCreateAudPlanJob}
                        disabled={isCreatingAudPlanJob}
                      >
                        {isCreatingAudPlanJob ? "Creating..." : "Generate AUD Plan"}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handleCreateOpenPointsJob}
                        disabled={isCreatingOpenPointsJob}
                      >
                        {isCreatingOpenPointsJob
                          ? "Creating..."
                          : "Extract Open Points"}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handleCreateEvidenceIndexJob}
                        disabled={isCreatingEvidenceIndexJob}
                      >
                        {isCreatingEvidenceIndexJob
                          ? "Creating..."
                          : "Build Evidence Index"}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handleCreateSourceSummariesJob}
                        disabled={isCreatingSourceSummariesJob}
                      >
                        {isCreatingSourceSummariesJob
                          ? "Creating..."
                          : "Generate AI Source Summaries"}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handleCreateSectionDraftsJob}
                        disabled={isCreatingSectionDraftsJob}
                      >
                        {isCreatingSectionDraftsJob
                          ? "Creating..."
                          : "Generate AI Section Drafts"}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handleCreateDocxJob}
                        disabled={isCreatingDocxJob}
                      >
                        {isCreatingDocxJob ? "Creating..." : "Generate DOCX"}
                      </button>
                    </div>
                  </details>

                  <div className="button-group section-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => refreshJobs(params.projectId)}
                      disabled={isLoadingJobs}
                    >
                      Refresh Jobs
                    </button>
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
                </div>
              ) : null}
            </section>

            <section className="panel" aria-labelledby="aud-plan-title">
              <div className="section-heading">
                <div>
                  <h2 id="aud-plan-title">AUD Plan</h2>
                  <p className="muted-text">
                    Review the planned AUD sections before document generation begins.
                  </p>
                </div>

                {renderSectionToggle("aud-plan")}
              </div>

              {isSectionExpanded("aud-plan") ? (
                <div className="panel-content">
                  <div className="button-group section-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => refreshAudPlan(params.projectId)}
                      disabled={isLoadingAudPlan}
                    >
                      Refresh AUD Plan
                    </button>
                  </div>

                  {audPlanMessage ? (
                    <p className="status-message">{audPlanMessage}</p>
                  ) : null}

                  {isLoadingAudPlan ? (
                    <p className="muted-text">Loading AUD plan...</p>
                  ) : null}

                  {!isLoadingAudPlan && !audPlan ? (
                    <p className="muted-text">No AUD plan generated yet.</p>
                  ) : null}

                  {!isLoadingAudPlan && audPlan ? (
                    <div className="aud-plan-content">
                      <dl className="aud-plan-meta">
                        <div>
                          <dt>Status</dt>
                          <dd>{audPlan.status}</dd>
                        </div>
                        <div>
                          <dt>Default Template Required</dt>
                          <dd>
                            {typeof audPlanJson.default_template_required === "boolean"
                              ? audPlanJson.default_template_required
                                ? "Yes"
                                : "No"
                              : "Not available"}
                          </dd>
                        </div>
                        <div>
                          <dt>Updated</dt>
                          <dd>{formatProjectDate(audPlan.updated_at)}</dd>
                        </div>
                      </dl>

                      {plannedSections.length === 0 ? (
                        <p className="muted-text">No planned sections available.</p>
                      ) : null}

                      <div className="aud-plan-section-list">
                        {plannedSections.map((section) => (
                          <article
                            key={section.section_id}
                            className="aud-plan-section-row"
                          >
                            <div>
                              <h3>{section.title}</h3>
                              <p>{section.section_id}</p>
                            </div>

                            <dl className="aud-plan-section-meta">
                              <div>
                                <dt>Confidence</dt>
                                <dd>{section.confidence}</dd>
                              </div>
                              <div>
                                <dt>Include in AUD</dt>
                                <dd>{section.include_in_aud ? "Yes" : "No"}</dd>
                              </div>
                              <div>
                                <dt>Source Role Basis</dt>
                                <dd>{formatPrioritySource(section.source_role_basis)}</dd>
                              </div>
                            </dl>

                            <div className="aud-plan-notes">
                              <h4>Notes</h4>
                              {section.notes.length > 0 ? (
                                <ul>
                                  {section.notes.map((note) => (
                                    <li key={note}>{note}</li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="muted-text">No notes.</p>
                              )}
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>

            <section className="panel" aria-labelledby="open-points-title">
              <div className="section-heading">
                <div>
                  <h2 id="open-points-title">Open Points</h2>
                  <p className="muted-text">
                    Review unresolved questions extracted from project sources.
                  </p>
                </div>

                {renderSectionToggle("open-points")}
              </div>

              {isSectionExpanded("open-points") ? (
                <div className="panel-content">
                  <div className="button-group section-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => refreshOpenPoints(params.projectId)}
                      disabled={isLoadingOpenPoints}
                    >
                      Refresh Open Points
                    </button>
                  </div>

                  {openPointsMessage ? (
                    <p className="status-message">{openPointsMessage}</p>
                  ) : null}

                  {isLoadingOpenPoints ? (
                    <p className="muted-text">Loading open points...</p>
                  ) : null}

                  {!isLoadingOpenPoints && openPoints.length === 0 ? (
                    <p className="muted-text">No open points extracted yet.</p>
                  ) : null}

                  {!isLoadingOpenPoints && openPoints.length > 0 ? (
                    <div className="open-points-table-wrap">
                      <table className="open-points-table">
                        <thead>
                          <tr>
                            <th scope="col">#</th>
                            <th scope="col">Topic</th>
                            <th scope="col">Question</th>
                            <th scope="col">Status</th>
                            <th scope="col">Evidence Preview</th>
                          </tr>
                        </thead>
                        <tbody>
                          {openPoints.map((openPoint, index) => (
                            <tr key={openPoint.id}>
                              <td>{index + 1}</td>
                              <td>{openPoint.topic}</td>
                              <td>{openPoint.question}</td>
                              <td>{openPoint.status}</td>
                              <td>{buildEvidencePreview(openPoint.evidence)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>

            <section className="panel" aria-labelledby="source-priority-title">
              <div className="section-heading">
                <div>
                  <h2 id="source-priority-title">Source Priority</h2>
                  <p className="muted-text">
                    Review source precedence rules before AUD generation begins.
                  </p>
                </div>

                {renderSectionToggle("source-priority")}
              </div>

              {isSectionExpanded("source-priority") ? (
                <div className="panel-content">
                  <div className="button-group section-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => refreshSourcePriority(params.projectId)}
                      disabled={isLoadingSourcePriority}
                    >
                      Refresh Source Priority
                    </button>
                  </div>

                  {sourcePriorityMessage ? (
                    <p className="status-message">{sourcePriorityMessage}</p>
                  ) : null}

                  {isLoadingSourcePriority ? (
                    <p className="muted-text">Loading source priority...</p>
                  ) : null}

                  {!isLoadingSourcePriority && sourcePriorityReport ? (
                    <div className="source-priority-content">
                      <dl className="source-priority-meta">
                        <div>
                          <dt>Explicit Template</dt>
                          <dd>
                            {sourcePriorityReport.has_explicit_template ? "Yes" : "No"}
                          </dd>
                        </div>
                        <div>
                          <dt>FDD Golden Source</dt>
                          <dd>
                            {sourcePriorityReport.golden_source_files.length > 0
                              ? "Yes"
                              : "No"}
                          </dd>
                        </div>
                        <div>
                          <dt>Default SCM Template Needed</dt>
                          <dd>
                            {sourcePriorityReport.recommended_default_template_needed
                              ? "Yes"
                              : "No"}
                          </dd>
                        </div>
                      </dl>

                      <div className="source-priority-block">
                        <h3>Source Roles Present</h3>
                        <p>
                          {sourcePriorityReport.source_roles_present.length > 0
                            ? sourcePriorityReport.source_roles_present
                                .map((role) => formatSourceRole(role))
                                .join(", ")
                            : "Not available"}
                        </p>
                      </div>

                      <div className="source-priority-block">
                        <h3>Priority Order</h3>
                        {sourcePriorityReport.priority_order.length > 0 ? (
                          <ol className="priority-list">
                            {sourcePriorityReport.priority_order.map((item) => (
                              <li key={`${item.priority}-${item.source}`}>
                                <strong>{formatPrioritySource(item.source)}</strong>
                                <span>{item.purpose}</span>
                                <p>{item.rule}</p>
                              </li>
                            ))}
                          </ol>
                        ) : (
                          <p className="muted-text">No priority order available.</p>
                        )}
                      </div>

                      <div className="source-priority-block">
                        <h3>Warnings</h3>
                        {sourcePriorityReport.warnings.length > 0 ? (
                          <ul className="warning-list">
                            {sourcePriorityReport.warnings.map((warning) => (
                              <li key={warning}>{warning}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="muted-text">No warnings.</p>
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>

            <section className="panel" aria-labelledby="evidence-index-title">
              <div className="section-heading">
                <div>
                  <h2 id="evidence-index-title">Evidence Index</h2>
                  <p className="muted-text">
                    Review normalized evidence packets for future AUD planning and drafting.
                  </p>
                </div>

                {renderSectionToggle("evidence-index")}
              </div>

              {isSectionExpanded("evidence-index") ? (
                <div className="panel-content">
                  <div className="button-group section-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => refreshEvidenceItems(params.projectId)}
                      disabled={isLoadingEvidenceItems}
                    >
                      Refresh Evidence
                    </button>
                  </div>

                  {evidenceItemsMessage ? (
                    <p className="status-message">{evidenceItemsMessage}</p>
                  ) : null}

                  {isLoadingEvidenceItems ? (
                    <p className="muted-text">Loading evidence index...</p>
                  ) : null}

                  {!isLoadingEvidenceItems && evidenceItems.length === 0 ? (
                    <p className="muted-text">No evidence items built yet.</p>
                  ) : null}

                  {!isLoadingEvidenceItems && evidenceItems.length > 0 ? (
                    <div className="evidence-index-content">
                      <div className="evidence-summary-grid" aria-label="Evidence counts">
                        {evidenceGroupCounts.map((group) => (
                          <article
                            key={`${group.evidenceType}-${group.sourceRole || "unknown"}`}
                            className="evidence-count-card"
                          >
                            <strong>{group.count}</strong>
                            <span>{group.evidenceType}</span>
                            <p>{formatSourceRole(group.sourceRole)}</p>
                          </article>
                        ))}
                      </div>

                      <div className="evidence-items-block">
                        <h3>Top Evidence Items</h3>

                        <div className="evidence-item-list">
                          {topEvidenceItems.map((item) => (
                            <article key={item.id} className="evidence-item-row">
                              <div>
                                <h4>{item.title || "Untitled evidence item"}</h4>
                                <p>{buildEvidencePreview(item.text)}</p>
                              </div>

                              <dl className="evidence-item-meta">
                                <div>
                                  <dt>Evidence Type</dt>
                                  <dd>{item.evidence_type}</dd>
                                </div>
                                <div>
                                  <dt>Source Role</dt>
                                  <dd>{formatSourceRole(item.source_role)}</dd>
                                </div>
                                <div>
                                  <dt>Priority</dt>
                                  <dd>{item.priority}</dd>
                                </div>
                                <div>
                                  <dt>Confidence</dt>
                                  <dd>{item.confidence}</dd>
                                </div>
                              </dl>
                            </article>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>

            <section className="panel" aria-labelledby="source-summaries-title">
              <div className="section-heading">
                <div>
                  <h2 id="source-summaries-title">Source Summaries</h2>
                  <p className="muted-text">
                    Review AI summaries grouped by source role before later AUD refinement.
                  </p>
                </div>

                {renderSectionToggle("source-summaries")}
              </div>

              {isSectionExpanded("source-summaries") ? (
                <div className="panel-content">
                  <div className="button-group section-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => refreshSourceSummaries(params.projectId)}
                      disabled={isLoadingSourceSummaries}
                    >
                      Refresh Source Summaries
                    </button>
                  </div>

                  {sourceSummariesMessage ? (
                    <p className="status-message">{sourceSummariesMessage}</p>
                  ) : null}

                  {isLoadingSourceSummaries ? (
                    <p className="muted-text">Loading source summaries...</p>
                  ) : null}

                  {!isLoadingSourceSummaries && sourceSummaries.length === 0 ? (
                    <p className="muted-text">No source summaries generated yet.</p>
                  ) : null}

                  {!isLoadingSourceSummaries && sourceSummaries.length > 0 ? (
                    <div className="source-summary-group-list">
                      {sourceSummaryGroups.map(([role, summaries]) => (
                        <section key={role} className="source-summary-group">
                          <h3>{formatSourceRole(role)}</h3>

                          <div className="source-summary-list">
                            {summaries.map((summary) => {
                              const summaryJson = parseSourceSummaryJson(
                                summary.summary_json,
                              );

                              return (
                                <article
                                  key={summary.id}
                                  className="source-summary-row"
                                >
                                  <div>
                                    <h4>{summary.summary_type}</h4>
                                    <p>{summary.summary_text}</p>
                                  </div>

                                  <dl className="source-summary-meta">
                                    <div>
                                      <dt>Source Role</dt>
                                      <dd>{formatSourceRole(summary.source_role)}</dd>
                                    </div>
                                    <div>
                                      <dt>Summary Type</dt>
                                      <dd>{summary.summary_type}</dd>
                                    </div>
                                    <div>
                                      <dt>Confidence</dt>
                                      <dd>
                                        {summaryJson.source_confidence ||
                                          "Not available"}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt>Important Topics</dt>
                                      <dd>
                                        {formatSummaryList(
                                          summaryJson.important_topics,
                                        )}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt>Usage Guidance</dt>
                                      <dd>
                                        {summaryJson.aud_usage_guidance ||
                                          "Not available"}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt>Open / Unresolved Items</dt>
                                      <dd>
                                        {formatSummaryList(
                                          summaryJson.open_or_unresolved_items,
                                        )}
                                      </dd>
                                    </div>
                                  </dl>
                                </article>
                              );
                            })}
                          </div>
                        </section>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>

            <section className="panel" aria-labelledby="section-drafts-title">
              <div className="section-heading">
                <div>
                  <h2 id="section-drafts-title">Section Drafts</h2>
                  <p className="muted-text">
                    Review AI-generated section drafts prepared from bounded evidence packs.
                  </p>
                </div>

                {renderSectionToggle("section-drafts")}
              </div>

              {isSectionExpanded("section-drafts") ? (
                <div className="panel-content">
                  <p className="review-note">
                    AI draft requires senior consultant review before customer sharing.
                  </p>

                  <div className="button-group section-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => refreshSectionDrafts(params.projectId)}
                      disabled={isLoadingSectionDrafts}
                    >
                      Refresh Section Drafts
                    </button>
                  </div>

                  {sectionDraftsMessage ? (
                    <p className="status-message">{sectionDraftsMessage}</p>
                  ) : null}

                  {isLoadingSectionDrafts ? (
                    <p className="muted-text">Loading section drafts...</p>
                  ) : null}

                  {!isLoadingSectionDrafts && sectionDrafts.length === 0 ? (
                    <p className="muted-text">No section drafts generated yet.</p>
                  ) : null}

                  {!isLoadingSectionDrafts && sectionDrafts.length > 0 ? (
                    <div className="section-draft-group-list">
                      {orderedSectionDraftGroups.map((group) => (
                        <section key={group.sectionId} className="section-draft-group">
                          <h3>
                            {group.order}. {group.title}
                          </h3>

                          <div className="section-draft-list">
                            {group.drafts.map((draft) => {
                              const draftJson = parseSectionDraftJson(
                                draft.draft_json,
                              );
                              const unsupportedDetails =
                                draftJson.unsupported_details ?? [];
                              const placeholders = draftJson.placeholders ?? [];
                              const openPointCandidates =
                                draftJson.open_point_candidates ?? [];
                              const fullTextKey = `section-draft-text-${draft.id}`;

                              return (
                                <article key={draft.id} className="section-draft-row">
                                  <div>
                                    <h4>{draft.title}</h4>
                                    <p>{buildDraftPreview(draft.draft_text)}</p>
                                  </div>

                                  <dl className="section-draft-meta">
                                    <div>
                                      <dt>Confidence</dt>
                                      <dd>{draft.confidence}</dd>
                                    </div>
                                    <div>
                                      <dt>Review Status</dt>
                                      <dd>{draft.review_status}</dd>
                                    </div>
                                    <div>
                                      <dt>Section ID</dt>
                                      <dd>{draft.section_id}</dd>
                                    </div>
                                    <div>
                                      <dt>Updated</dt>
                                      <dd>{formatProjectDate(draft.updated_at)}</dd>
                                    </div>
                                  </dl>

                                  <div className="button-group section-draft-actions">
                                    <button
                                      type="button"
                                      className="secondary-button"
                                      onClick={() => toggleSection(fullTextKey)}
                                      aria-expanded={isSectionExpanded(fullTextKey)}
                                    >
                                      {isSectionExpanded(fullTextKey)
                                        ? "Collapse Full Text"
                                        : "Expand Full Text"}
                                    </button>
                                  </div>

                                  {isSectionExpanded(fullTextKey) ? (
                                    <pre className="section-draft-full-text">
                                      {draft.draft_text}
                                    </pre>
                                  ) : null}

                                  <div className="section-draft-detail-grid">
                                    <div className="section-draft-detail-block">
                                      <h5>Unsupported Details</h5>
                                      {unsupportedDetails.length > 0 ? (
                                        <ul>
                                          {unsupportedDetails.map((item, index) => (
                                            <li key={`${draft.id}-unsupported-${index}`}>
                                              {formatDraftDetail(item)}
                                            </li>
                                          ))}
                                        </ul>
                                      ) : (
                                        <p className="muted-text">None reported.</p>
                                      )}
                                    </div>

                                    <div className="section-draft-detail-block">
                                      <h5>Placeholders</h5>
                                      {placeholders.length > 0 ? (
                                        <ul>
                                          {placeholders.map((item, index) => (
                                            <li key={`${draft.id}-placeholder-${index}`}>
                                              {formatDraftDetail(item)}
                                            </li>
                                          ))}
                                        </ul>
                                      ) : (
                                        <p className="muted-text">None reported.</p>
                                      )}
                                    </div>

                                    <div className="section-draft-detail-block">
                                      <h5>Open Point Candidates</h5>
                                      {openPointCandidates.length > 0 ? (
                                        <ul>
                                          {openPointCandidates.map((item, index) => (
                                            <li key={`${draft.id}-open-point-${index}`}>
                                              {formatDraftDetail(item)}
                                            </li>
                                          ))}
                                        </ul>
                                      ) : (
                                        <p className="muted-text">None reported.</p>
                                      )}
                                    </div>
                                  </div>
                                </article>
                              );
                            })}
                          </div>
                        </section>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>

            <section className="panel" aria-labelledby="extracted-content-title">
              <div className="section-heading">
                <div>
                  <h2 id="extracted-content-title">Extracted Content</h2>
                  <p className="muted-text">
                    Review extracted source records before AUD generation begins.
                  </p>
                </div>

                {renderSectionToggle("extracted-content")}
              </div>

              {isSectionExpanded("extracted-content") ? (
                <div className="panel-content">
                  <div className="button-group section-actions">
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
                      const jsonContent = parseExtractedContentJson(
                        content.json_content,
                      );

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
                </div>
              ) : null}
            </section>

            <section className="panel" aria-labelledby="generated-documents-title">
              <div className="section-heading">
                <div>
                  <h2 id="generated-documents-title">Generated Documents</h2>
                  <p className="muted-text">
                    Generate and download editable AUD drafts for internal review.
                  </p>
                </div>

                {renderSectionToggle("generated-documents")}
              </div>

              {isSectionExpanded("generated-documents") ? (
                <div className="panel-content">
                  <div className="button-group section-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => refreshGeneratedDocuments(params.projectId)}
                      disabled={isLoadingGeneratedDocuments}
                    >
                      Refresh Documents
                    </button>
                  </div>

                  {generatedDocumentsMessage ? (
                    <p className="status-message">{generatedDocumentsMessage}</p>
                  ) : null}

                  {isLoadingGeneratedDocuments ? (
                    <p className="muted-text">Loading generated documents...</p>
                  ) : null}

                  {!isLoadingGeneratedDocuments && generatedDocuments.length === 0 ? (
                    <p className="muted-text">No generated documents yet.</p>
                  ) : null}

                  <div className="generated-document-list">
                    {orderedGeneratedDocuments.map((document) => (
                      <article key={document.id} className="generated-document-row">
                        <div>
                          <h3>{document.filename}</h3>
                          <p>{document.document_type}</p>
                        </div>

                        <dl className="generated-document-meta">
                          <div>
                            <dt>Created</dt>
                            <dd>{formatProjectDate(document.created_at)}</dd>
                          </div>
                          <div>
                            <dt>Download</dt>
                            <dd>
                              <a
                                className="download-link"
                                href={getGeneratedDocumentDownloadUrl(
                                  params.projectId,
                                  document.id,
                                )}
                              >
                                Download DOCX
                              </a>
                            </dd>
                          </div>
                        </dl>
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}
            </section>
          </>
        ) : null}
      </section>
    </main>
  );
}
