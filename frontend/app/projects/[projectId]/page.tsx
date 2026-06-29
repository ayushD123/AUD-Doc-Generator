"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

import { AudacleSelect, type AudacleSelectOption } from "@/components/AudacleSelect";
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

type Theme = "light" | "dark";

const pendingUploadIdPrefix = "pending-upload-";
const themeStorageKey = "audacle-theme";
const sourceRoleDescriptions: Partial<Record<SourceRole, string>> = {
  fdd: "Primary functional design source",
  kt_ppt: "Knowledge transfer slide deck",
  config_workbook: "Setup and configuration data",
  unknown: "Additional supporting files",
};

function Icon({
  name,
  className,
}: {
  name:
    | "arrow-left"
    | "calendar"
    | "chevron-down"
    | "chevron-up"
    | "cube"
    | "edit"
    | "info"
    | "mail"
    | "moon"
    | "sparkles"
    | "tag"
    | "user"
    | "users"
    | "sun";
  className?: string;
}) {
  const paths = {
    "arrow-left": <path d="M19 12H5M12 19l-7-7 7-7" />,
    calendar: (
      <>
        <path d="M7 3v3M17 3v3M4.5 8.2h15" />
        <path d="M5.8 5.2h12.4c.9 0 1.6.7 1.6 1.6v11.4c0 .9-.7 1.6-1.6 1.6H5.8c-.9 0-1.6-.7-1.6-1.6V6.8c0-.9.7-1.6 1.6-1.6Z" />
      </>
    ),
    "chevron-down": <path d="m6 9 6 6 6-6" />,
    "chevron-up": <path d="m18 15-6-6-6 6" />,
    cube: (
      <>
        <path d="m12 3 7.5 4.2v9.6L12 21l-7.5-4.2V7.2Z" />
        <path d="m4.5 7.2 7.5 4.3 7.5-4.3M12 21v-9.5" />
      </>
    ),
    edit: (
      <>
        <path d="M12 20h8" />
        <path d="m16.8 3.6 3.6 3.6L8.4 19.2l-4.4.8.8-4.4Z" />
      </>
    ),
    info: (
      <>
        <path d="M12 17v-6" />
        <path d="M12 8h.01" />
        <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z" />
      </>
    ),
    mail: (
      <>
        <path d="M4.5 6.5h15v11h-15Z" />
        <path d="m5 7 7 5.5L19 7" />
      </>
    ),
    moon: <path d="M20.2 14.3A7.6 7.6 0 0 1 9.7 3.8 8.2 8.2 0 1 0 20.2 14.3Z" />,
    sparkles: (
      <>
        <path d="M12 3.5 13.7 8 18 9.7 13.7 11.4 12 16l-1.7-4.6L6 9.7 10.3 8Z" />
        <path d="M19 15.5 20 18l2.5 1-2.5 1-1 2.5-1-2.5-2.5-1 2.5-1Z" />
      </>
    ),
    tag: (
      <>
        <path d="M20 13.5 13.5 20 4 10.5V4h6.5Z" />
        <path d="M8.5 8.5h.01" />
      </>
    ),
    user: (
      <>
        <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
        <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
      </>
    ),
    users: (
      <>
        <path d="M9.5 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
        <path d="M3.5 20a6 6 0 0 1 12 0" />
        <path d="M17 9.5a3 3 0 0 0-2-5.2M17.5 19.5a5 5 0 0 0-3-4.6" />
      </>
    ),
    sun: (
      <>
        <path d="M12 3v2M12 19v2M5.6 5.6 7 7M17 17l1.4 1.4M3 12h2M19 12h2M5.6 18.4 7 17M17 7l1.4-1.4" />
        <path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z" />
      </>
    ),
  };

  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

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
    id: `${pendingUploadIdPrefix}${createPendingUploadId()}`,
    project_id: projectId,
    original_filename: file.name || "uploaded_file",
    file_type: getClientFileType(file.name),
    storage_path: "",
    source_role: sourceRole,
    created_at: new Date().toISOString(),
    uploadStatus: "pending",
  };
}

function createPendingUploadId() {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    // Public HTTP deployments may not expose crypto.randomUUID().
  }

  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function isPendingUploadedFile(uploadedFile: UploadedFileListItem) {
  return uploadedFile.uploadStatus === "pending";
}

function getUploadedFileExtension(uploadedFile: UploadedFileListItem) {
  const explicitType = uploadedFile.file_type?.trim();

  if (explicitType) {
    return explicitType.replace(/^\./, "").toUpperCase();
  }

  const extension = getClientFileType(uploadedFile.original_filename);
  return extension ? extension.toUpperCase() : "FILE";
}

function getFileTypeVariant(fileType: string | null | undefined) {
  const normalizedType = fileType?.toLowerCase();

  if (normalizedType === "pdf") {
    return "pdf";
  }

  if (normalizedType === "docx" || normalizedType === "doc") {
    return "doc";
  }

  if (normalizedType === "xlsx" || normalizedType === "xls" || normalizedType === "csv") {
    return "sheet";
  }

  if (normalizedType === "pptx" || normalizedType === "ppt") {
    return "slide";
  }

  if (normalizedType === "zip") {
    return "zip";
  }

  if (normalizedType === "txt") {
    return "text";
  }

  if (
    normalizedType === "mp3" ||
    normalizedType === "mp4" ||
    normalizedType === "mov" ||
    normalizedType === "wav"
  ) {
    return "media";
  }

  return "generic";
}

function getSourceRoleVariant(sourceRole: SourceRole | null | undefined) {
  if (sourceRole === "fdd") {
    return "functional";
  }

  if (sourceRole === "kt_ppt" || sourceRole === "kt_session" || sourceRole === "kt_transcript") {
    return "technical";
  }

  if (sourceRole === "config_workbook") {
    return "data";
  }

  if (sourceRole === "aud_template" || sourceRole === "template_aud" || sourceRole === "final_aud_sample") {
    return "template";
  }

  if (sourceRole === "supporting_doc") {
    return "supporting";
  }

  return "other";
}

function buildSourceRoleOptions(): AudacleSelectOption[] {
  return sourceRoles.map((role) => ({
    value: role,
    label: sourceRoleLabels[role],
    description: sourceRoleDescriptions[role],
    icon: (
      <span
        className={`audacle-select-role-dot audacle-select-role-dot-${getSourceRoleVariant(role)}`}
        aria-hidden="true"
      />
    ),
  }));
}

function splitFormattedDateTime(value: string) {
  const trimmedValue = value.trim();
  const timeMatch = trimmedValue.match(/\b\d{1,2}:\d{2}(?:\s?[AP]M)?\b/i);

  if (!timeMatch || timeMatch.index === undefined) {
    return {
      date: trimmedValue,
      time: null,
    };
  }

  return {
    date: trimmedValue.slice(0, timeMatch.index).replace(/[,\s]+$/, ""),
    time: trimmedValue.slice(timeMatch.index).trim(),
  };
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
    return "None";
  }

  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const audGenerationStages = [
  {
    key: "validate_project_inputs",
    label: "Validate Project Inputs",
    description: "Validating project configuration and uploaded files...",
  },
  {
    key: "extract_content",
    label: "Extract Content",
    description: "Extracting content from uploaded documents...",
  },
  {
    key: "enrich_document_understanding",
    label: "Enrich Document Understanding",
    description: "Enriching content using Document Understanding...",
  },
  {
    key: "transcribe_media",
    label: "Transcribe Media",
    description: "Transcribing media files such as audio or video...",
  },
  {
    key: "generate_initial_aud_plan",
    label: "Generate Initial AUD Plan",
    description: "Creating the first structured AUD plan...",
  },
  {
    key: "build_evidence_index",
    label: "Build Evidence Index",
    description: "Building normalized evidence from extracted content...",
  },
  {
    key: "generate_source_summaries_ai",
    label: "Generate Source Summaries AI",
    description: "Generating AI-assisted source summaries...",
  },
  {
    key: "enhance_aud_plan_ai",
    label: "Enhance AUD Plan AI",
    description: "Refining the AUD plan using AI assistance...",
  },
  {
    key: "build_section_evidence_packs",
    label: "Build Section Evidence Packs",
    description: "Preparing section-specific evidence packets...",
  },
  {
    key: "generate_open_points_ai",
    label: "Generate Open Points AI",
    description: "Identifying unresolved questions and open points...",
  },
  {
    key: "generate_section_drafts_ai",
    label: "Generate Section Drafts AI",
    description: "Drafting AUD sections from approved evidence packs...",
  },
  {
    key: "generate_final_docx",
    label: "Generate Final DOCX",
    description: "Creating the final editable AUD DOCX document...",
  },
];

const audGenerationStageAliases: Record<string, string> = {
  generate_docx: "generate_final_docx",
};

type AudGenerationStage = (typeof audGenerationStages)[number];
type AudGenerationStageDisplayStatus =
  | "completed"
  | "in-progress"
  | "failed"
  | "pending";

function getAudGenerationModalTitle(status: string | null | undefined) {
  if (status === "completed") {
    return "AUD Generation Completed";
  }

  if (status === "completed_with_warnings") {
    return "AUD Generation Completed with Warnings";
  }

  if (status === "failed") {
    return "AUD Generation Failed";
  }

  if (status && !isAudGenerationTerminal(status)) {
    return "AUD Generation in Progress";
  }

  return "AUD Generation Progress";
}

function getAudGenerationModalSubtitle(status: string | null | undefined) {
  if (status === "completed") {
    return "Your final AUD document is ready for review and download.";
  }

  if (status === "completed_with_warnings") {
    return "Your final AUD document is ready, but some warnings require review.";
  }

  if (status === "failed") {
    return "AUD generation stopped before completion. Review the failed stage and error details below.";
  }

  return "We’re generating your AUD and will notify you by email when it’s complete";
}

function getAudGenerationSummary(status: AUDGenerationStatus | null) {
  if (!status) {
    return "AUD generation has not started yet.";
  }

  if (status.status === "completed") {
    return "Final AUD is ready.";
  }

  if (status.status === "completed_with_warnings") {
    return "Final AUD is ready with warnings.";
  }

  if (status.status === "failed") {
    return "AUD generation failed.";
  }

  return "AUD generation is currently running.";
}

function getAudGenerationPillLabel(status: string | null | undefined) {
  if (status === "completed") {
    return "Completed";
  }

  if (status === "completed_with_warnings") {
    return "Completed with warnings";
  }

  if (status === "failed") {
    return "Failed";
  }

  if (status && !isAudGenerationTerminal(status)) {
    return "Running";
  }

  return "Not started";
}

function normalizeAudGenerationStageKey(stageKey: string | null | undefined) {
  if (!stageKey) {
    return null;
  }

  return audGenerationStageAliases[stageKey] ?? stageKey;
}

function getKnownStageLabel(stageKey: string) {
  const normalizedStageKey = normalizeAudGenerationStageKey(stageKey) ?? stageKey;

  return (
    audGenerationStages.find((stage) => stage.key === normalizedStageKey)?.label ??
    formatStageLabel(stageKey)
  );
}

function getKnownStageDescription(stageKey: string) {
  const normalizedStageKey = normalizeAudGenerationStageKey(stageKey) ?? stageKey;

  return (
    audGenerationStages.find((stage) => stage.key === normalizedStageKey)?.description ??
    "Processing this AUD pipeline stage..."
  );
}

function getAudGenerationDisplayStages(
  status: AUDGenerationStatus | null,
): AudGenerationStage[] {
  const knownStageKeys = new Set(audGenerationStages.map((stage) => stage.key));
  const backendStages = [
    ...(status?.completed_stages ?? []),
    status?.current_stage,
    status?.failed_stage,
  ]
    .map(normalizeAudGenerationStageKey)
    .filter((stage): stage is string => Boolean(stage));
  const unknownStages = Array.from(new Set(backendStages)).filter(
    (stage) => !knownStageKeys.has(stage),
  );

  return [
    ...audGenerationStages,
    ...unknownStages.map((stage) => ({
      key: stage,
      label: formatStageLabel(stage),
      description: getKnownStageDescription(stage),
    })),
  ];
}

function getStageDisplayStatus(
  stageKey: string,
  status: AUDGenerationStatus | null,
): AudGenerationStageDisplayStatus {
  if (!status) {
    return "pending";
  }

  const normalizedStageKey = normalizeAudGenerationStageKey(stageKey) ?? stageKey;
  const normalizedFailedStage = normalizeAudGenerationStageKey(status.failed_stage);
  const normalizedCurrentStage = normalizeAudGenerationStageKey(status.current_stage);
  const normalizedCompletedStages = status.completed_stages
    .map(normalizeAudGenerationStageKey)
    .filter((completedStage): completedStage is string => Boolean(completedStage));

  if (
    normalizedFailedStage === normalizedStageKey ||
    (status.status === "failed" && normalizedCurrentStage === normalizedStageKey)
  ) {
    return "failed";
  }

  if (normalizedCompletedStages.includes(normalizedStageKey)) {
    return "completed";
  }

  if (isAudGenerationSuccess(status.status)) {
    return "completed";
  }

  if (normalizedCurrentStage === normalizedStageKey && !isAudGenerationTerminal(status.status)) {
    return "in-progress";
  }

  return "pending";
}

function getStageProgressPercent(status: AUDGenerationStatus | null) {
  if (!status) {
    return 0;
  }

  const totalStages = getAudGenerationDisplayStages(status).length;
  if (totalStages === 0) {
    return 0;
  }

  if (status.status === "completed" || status.status === "completed_with_warnings") {
    return 100;
  }

  return Math.round((getCompletedDisplayStageCount(status) / totalStages) * 100);
}

function getCompletedDisplayStageCount(status: AUDGenerationStatus | null) {
  if (!status) {
    return 0;
  }

  const displayStages = getAudGenerationDisplayStages(status);

  if (isAudGenerationSuccess(status.status)) {
    return displayStages.length;
  }

  const normalizedCompletedStages = new Set(
    status.completed_stages
      .map(normalizeAudGenerationStageKey)
      .filter((stage): stage is string => Boolean(stage)),
  );

  return displayStages.filter((stage) => normalizedCompletedStages.has(stage.key)).length;
}

type AudGenerationProgressModalProps = {
  isOpen: boolean;
  onClose: () => void;
  audGenerationStatus: AUDGenerationStatus | null;
  isLoadingAudGenerationStatus: boolean;
  audGenerationMessage: string | null;
};

function AudGenerationProgressModal({
  isOpen,
  onClose,
  audGenerationStatus,
  isLoadingAudGenerationStatus,
  audGenerationMessage,
}: AudGenerationProgressModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const displayStages = getAudGenerationDisplayStages(audGenerationStatus);
  const completedCount = getCompletedDisplayStageCount(audGenerationStatus);
  const progressPercent = getStageProgressPercent(audGenerationStatus);
  const isTerminal = isAudGenerationTerminal(audGenerationStatus?.status);
  const title = getAudGenerationModalTitle(audGenerationStatus?.status);
  const subtitle = getAudGenerationModalSubtitle(audGenerationStatus?.status);
  const progressTone =
    audGenerationStatus?.status === "failed"
      ? "failed"
      : isAudGenerationSuccess(audGenerationStatus?.status)
        ? "completed"
        : "running";

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="aud-progress-modal-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        className="aud-progress-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="aud-progress-modal-title"
        aria-describedby="aud-progress-modal-subtitle"
      >
        <div className="aud-progress-modal-header">
          <button
            ref={closeButtonRef}
            type="button"
            className="aud-progress-close-icon"
            onClick={onClose}
            aria-label="Close AUD generation progress"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>

          <h2 id="aud-progress-modal-title">{title}</h2>
          <p id="aud-progress-modal-subtitle">{subtitle}</p>

          <div
            className={`aud-progress-visual aud-progress-visual-${progressTone}`}
            aria-hidden="true"
          >
            <div className="aud-progress-cloud aud-progress-cloud-left" />
            <div className="aud-progress-cloud aud-progress-cloud-right" />
            <div className="aud-progress-document">
              <span />
              <span />
              <span />
              <span />
            </div>
            <div className="aud-progress-ring" />
          </div>
        </div>

        <div className="aud-progress-modal-body">
          {audGenerationMessage ? (
            <p className="aud-progress-message">{audGenerationMessage}</p>
          ) : null}

          <div className="aud-progress-summary">
            <dl>
              <div>
                <dt>Status</dt>
                <dd>{getAudGenerationPillLabel(audGenerationStatus?.status)}</dd>
              </div>
              <div>
                <dt>Current Stage</dt>
                <dd>{formatStageLabel(audGenerationStatus?.current_stage)}</dd>
              </div>
              {audGenerationStatus?.failed_stage ? (
                <div>
                  <dt>Failed Stage</dt>
                  <dd>{formatStageLabel(audGenerationStatus.failed_stage)}</dd>
                </div>
              ) : null}
              <div>
                <dt>Completed</dt>
                <dd>
                  {completedCount} of {displayStages.length} stages completed
                </dd>
              </div>
            </dl>

            <div
              className={`aud-progress-bar aud-progress-bar-${progressTone}`}
              aria-label={`${progressPercent}% complete`}
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progressPercent}
            >
              <span style={{ width: `${progressPercent}%` }} />
            </div>
          </div>

          {isLoadingAudGenerationStatus ? (
            <p className="muted-text">Refreshing AUD generation status...</p>
          ) : null}

          <ol className="aud-progress-timeline">
            {displayStages.map((stage, index) => {
              const stageStatus = getStageDisplayStatus(
                stage.key,
                audGenerationStatus,
              );
              const statusLabel =
                stageStatus === "in-progress"
                  ? "In Progress"
                  : stageStatus.charAt(0).toUpperCase() + stageStatus.slice(1);

              return (
                <li
                  key={stage.key}
                  className={`aud-progress-stage aud-progress-stage-${stageStatus}`}
                >
                  <div className="aud-progress-stage-marker" aria-hidden="true">
                    <span />
                  </div>
                  <div className="aud-progress-stage-content">
                    <div>
                      <h3>
                        {index + 1}. {getKnownStageLabel(stage.key)}
                      </h3>
                      <p>{stage.description}</p>
                    </div>
                    <span
                      className={`aud-progress-stage-pill aud-progress-stage-pill-${stageStatus}`}
                    >
                      {statusLabel}
                    </span>
                  </div>
                </li>
              );
            })}
          </ol>

          {audGenerationStatus?.warnings.length ? (
            <div className="aud-progress-callout aud-progress-callout-warning">
              <h3>Warnings</h3>
              <ul>
                {audGenerationStatus.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {audGenerationStatus?.status === "failed" ? (
            <div className="aud-progress-callout aud-progress-callout-error">
              <h3>Error</h3>
              <p>{audGenerationStatus.error || "Unknown backend error."}</p>
            </div>
          ) : null}
        </div>

        <footer className="aud-progress-modal-footer">
          <p>
            {audGenerationStatus?.status === "failed"
              ? "Generation failed. Review the error details or check Jobs / Debug Information."
              : isTerminal
                ? "Generation completed. Review the final document section for download."
                : "This may take a few minutes. You can safely close this window and continue working."}
          </p>
          <button type="button" className="secondary-button" onClick={onClose}>
            Close
          </button>
        </footer>
      </section>
    </div>
  );
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
  const [isAudProgressModalOpen, setIsAudProgressModalOpen] = useState(false);
  const [openFileActionMenuId, setOpenFileActionMenuId] = useState<string | null>(
    null,
  );
  const [theme, setTheme] = useState<Theme>("light");
  const [isThemeReady, setIsThemeReady] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>(
    {
      "project-details": true,
      "uploaded-files": true,
    },
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

  useEffect(() => {
    if (!openFileActionMenuId) {
      return;
    }

    function handleDocumentPointerDown(event: MouseEvent) {
      const target = event.target;

      if (
        target instanceof Element &&
        target.closest(".recent-file-actions")
      ) {
        return;
      }

      setOpenFileActionMenuId(null);
    }

    function handleDocumentKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenFileActionMenuId(null);
      }
    }

    document.addEventListener("mousedown", handleDocumentPointerDown);
    document.addEventListener("keydown", handleDocumentKeyDown);

    return () => {
      document.removeEventListener("mousedown", handleDocumentPointerDown);
      document.removeEventListener("keydown", handleDocumentKeyDown);
    };
  }, [openFileActionMenuId]);

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
      setIsAudProgressModalOpen(true);
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
  const hasUploadedFiles = uploadedFiles.length > 0;
  const hasPendingUploads = pendingUploadedFiles.length > 0;
  const generateAudDisabledHint = isLoadingFiles
    ? "Checking files"
    : hasPendingUploads
      ? "File uploading"
      : !hasUploadedFiles
        ? "Upload File First"
        : null;
  const isGenerateAudDisabled =
    isStartingAudGeneration || isAudGenerationRunning || Boolean(generateAudDisabledHint);
  const generateAudButtonLabel =
    isStartingAudGeneration || isAudGenerationRunning ? "Generating..." : "Generate AUD";
  const audGenerationProgressPercent = getStageProgressPercent(audGenerationStatus);
  const audGenerationStatusTone =
    audGenerationStatus?.status === "failed"
      ? "failed"
      : isAudGenerationSuccess(audGenerationStatus?.status)
        ? audGenerationStatus?.status === "completed_with_warnings"
          ? "warning"
          : "completed"
        : audGenerationStatus
          ? "running"
          : "pending";
  const isFinalAudReady = isAudGenerationSuccess(audGenerationStatus?.status);
  const finalAudPanelTone = isFinalAudReady ? "ready" : "draft";
  const projectHeaderStatusLabel = isFinalAudReady
    ? "Ready"
    : project?.status || "Draft";
  const projectHeaderStatusVariant = isFinalAudReady
    ? "ready"
    : projectHeaderStatusLabel.toLowerCase();
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
      <svg viewBox="0 0 24 24" aria-hidden="true">
        {isSectionExpanded(sectionKey) ? (
          <path d="m18 15-6-6-6 6" />
        ) : (
          <path d="m6 9 6 6 6-6" />
        )}
      </svg>
    </button>
  );

  return (
    <main className="audacle-dashboard project-detail-page" data-theme={theme}>
      <section className="workspace-panel detail-panel" aria-labelledby="project-title">
        {isLoading ? <p className="muted-text">Loading project...</p> : null}

        {message ? <p className="status-message status-error">{message}</p> : null}

        {project ? (
          <>
            <header className="project-hero">
              <div className="project-hero-main">
                <Link href="/" className="project-back-link">
                  <Icon name="arrow-left" />
                  Back to projects
                </Link>

                <div className="project-identity">
                  <span className="project-identity-icon" aria-hidden="true" />
                  <div className="project-title-stack">
                    <h1 id="project-title">
                      {project.customer_name || "Unnamed customer"}
                    </h1>
                    <div className="project-subtitle-row">
                      <p>{project.module_name || "No module selected"}</p>
                      <span
                        className={`project-status-pill project-status-${projectHeaderStatusVariant}`}
                      >
                        <span aria-hidden="true" />
                        {projectHeaderStatusLabel}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="project-hero-actions">
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

                <button
                  type="button"
                  className="project-edit-button"
                  disabled
                  title="Project editing is not available yet."
                >
                  <Icon name="edit" />
                  Edit Project
                </button>
              </div>
            </header>

            <section
              className="project-details-card"
              aria-labelledby="project-details-title"
            >
              <div className="project-details-header">
                <div className="project-details-heading">
                  <span className="project-details-icon" aria-hidden="true">
                    <Icon name="info" />
                  </span>
                  <div>
                    <h2 id="project-details-title">Project Details</h2>
                    <p>Overview and key information about this project.</p>
                  </div>
                </div>

                <div className="project-details-header-visual" aria-hidden="true" />

                <button
                  type="button"
                  className="secondary-button project-details-toggle"
                  onClick={() => toggleSection("project-details")}
                  aria-expanded={isSectionExpanded("project-details")}
                >
                  {isSectionExpanded("project-details") ? "Collapse" : "Expand"}
                  <Icon
                    name={
                      isSectionExpanded("project-details")
                        ? "chevron-up"
                        : "chevron-down"
                    }
                  />
                </button>
              </div>

              {isSectionExpanded("project-details") ? (
                <dl className="project-details-grid">
                  <div className="project-details-group">
                    <div className="project-detail-field">
                      <span className="project-detail-icon" aria-hidden="true">
                        <Icon name="user" />
                      </span>
                      <div>
                        <dt>Customer Name</dt>
                        <dd>{project.customer_name || "Not available"}</dd>
                      </div>
                    </div>
                    <div className="project-detail-field">
                      <span className="project-detail-icon" aria-hidden="true">
                        <Icon name="users" />
                      </span>
                      <div>
                        <dt>Author Name</dt>
                        <dd>{project.name || "Not available"}</dd>
                      </div>
                    </div>
                  </div>

                  <div className="project-details-group">
                    <div className="project-detail-field">
                      <span className="project-detail-icon" aria-hidden="true">
                        <Icon name="cube" />
                      </span>
                      <div>
                        <dt>Module Name</dt>
                        <dd>{project.module_name || "Not available"}</dd>
                      </div>
                    </div>
                    <div className="project-detail-field">
                      <span className="project-detail-icon" aria-hidden="true">
                        <Icon name="mail" />
                      </span>
                      <div>
                        <dt>Email ID</dt>
                        <dd>{project.email_id || "Not available"}</dd>
                      </div>
                    </div>
                  </div>

                  <div className="project-details-group">
                    <div className="project-detail-field">
                      <span className="project-detail-icon" aria-hidden="true">
                        <Icon name="calendar" />
                      </span>
                      <div>
                        <dt>Project Created</dt>
                        <dd>{formatProjectDate(project.created_at)}</dd>
                      </div>
                    </div>
                    <div className="project-detail-field">
                      <span className="project-detail-icon" aria-hidden="true">
                        <Icon name="tag" />
                      </span>
                      <div>
                        <dt>Project ID</dt>
                        <dd className="project-id-badge">{project.id}</dd>
                      </div>
                    </div>
                  </div>
                </dl>
              ) : null}
            </section>

            <section
              className={`panel final-aud-panel final-aud-panel-${finalAudPanelTone}`}
              aria-labelledby="final-aud-title"
            >
              <div className="section-heading">
                <div>
                  <h2 id="final-aud-title">Final Generated AUD DOCX</h2>
                  <p className="muted-text">
                    Download the latest generated AUD document.
                  </p>
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

                <span
                  className="generate-aud-button-shell"
                  data-tooltip={generateAudDisabledHint ?? undefined}
                >
                  <button
                    type="button"
                    className="primary-button generate-aud-button"
                    onClick={handleGenerateAud}
                    disabled={isGenerateAudDisabled}
                    aria-describedby={
                      generateAudDisabledHint ? "generate-aud-disabled-hint" : undefined
                    }
                  >
                    <Icon name="sparkles" />
                    <span className="generate-aud-button-copy">
                      <span>{generateAudButtonLabel}</span>
                      {generateAudDisabledHint ? (
                        <small>{generateAudDisabledHint}</small>
                      ) : null}
                    </span>
                  </button>
                  {generateAudDisabledHint ? (
                    <span id="generate-aud-disabled-hint" className="sr-only">
                      {generateAudDisabledHint}
                    </span>
                  ) : null}
                </span>
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

                {!isLoadingAudGenerationStatus ? (
                  <div className="aud-generation-compact-card">
                    <div className="aud-generation-compact-main">
                      <span
                        className={`aud-generation-status-pill aud-generation-status-pill-${audGenerationStatusTone}`}
                      >
                        {getAudGenerationPillLabel(audGenerationStatus?.status)}
                      </span>
                      <div>
                        <h3>{getAudGenerationSummary(audGenerationStatus)}</h3>
                        <p>
                          {audGenerationStatus?.status === "failed"
                            ? `Failed stage: ${formatStageLabel(
                                audGenerationStatus.failed_stage ||
                                  audGenerationStatus.current_stage,
                              )}`
                            : audGenerationStatus
                              ? `Current stage: ${formatStageLabel(
                                  audGenerationStatus.current_stage,
                                )}`
                              : "AUD generation has not started yet."}
                        </p>
                      </div>
                    </div>

                    {audGenerationStatus ? (
                      <div className="aud-generation-compact-actions">
                        <div
                          className={`aud-generation-mini-progress aud-generation-mini-progress-${audGenerationStatusTone}`}
                          aria-label={`${audGenerationProgressPercent}% complete`}
                          role="progressbar"
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuenow={audGenerationProgressPercent}
                        >
                          <span
                            style={{ width: `${audGenerationProgressPercent}%` }}
                          />
                        </div>
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => setIsAudProgressModalOpen(true)}
                        >
                          View Progress
                        </button>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </section>

            <section
              className="panel uploaded-files-panel"
              aria-labelledby="uploaded-files-title"
            >
              <div className="uploaded-files-header">
                <div className="uploaded-files-heading">
                  <span className="enterprise-icon-square" aria-hidden="true">
                    <svg viewBox="0 0 24 24">
                      <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7Z" />
                      <path d="M14 2v5h5" />
                      <path d="M12 17V9" />
                      <path d="m9 12 3-3 3 3" />
                    </svg>
                  </span>
                  <div>
                    <h2 id="uploaded-files-title">Uploaded Files</h2>
                    <p className="muted-text">
                      Upload and manage files for this project. Assign the correct
                      source role to help improve accuracy.
                    </p>
                  </div>
                </div>
                {renderSectionToggle("uploaded-files")}
              </div>

              {isSectionExpanded("uploaded-files") ? (
                <div className="panel-content uploaded-files-content">
                  <form className="enterprise-upload-form" onSubmit={handleUpload}>
                    <div className="upload-workspace-grid">
                      <div className="source-role-card">
                        <AudacleSelect
                          label="Source Role"
                          value={sourceRole}
                          options={buildSourceRoleOptions()}
                          disabled={isUploading}
                          onChange={(nextValue) => setSourceRole(nextValue as SourceRole)}
                          ariaLabel="Source role"
                          className="source-role-select"
                          leadingIcon={
                            <svg viewBox="0 0 24 24" aria-hidden="true">
                              <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7Z" />
                              <path d="M14 2v5h5" />
                              <path d="M9 13h6" />
                              <path d="M9 17h4" />
                            </svg>
                          }
                        />
                      </div>

                      <div className="file-upload-card">
                        <label htmlFor="project-file-input">File</label>
                        <div className="file-drop-zone">
                          <span className="file-drop-icon" aria-hidden="true">
                            <svg viewBox="0 0 24 24">
                              <path d="M12 16V8" />
                              <path d="m8 12 4-4 4 4" />
                              <path d="M20 16.5A4.5 4.5 0 0 0 15.5 12h-.7A6 6 0 1 0 4 15.5" />
                              <path d="M5 19h14" />
                            </svg>
                          </span>
                          <div className="file-drop-copy">
                            <strong>Drag and drop your file here</strong>
                            <span>or click to browse</span>
                          </div>
                          <div className="file-picker-row">
                            <label
                              className="secondary-button file-picker-button"
                              htmlFor="project-file-input"
                            >
                              <svg viewBox="0 0 24 24" aria-hidden="true">
                                <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 1 1-2.83-2.83l8.49-8.48" />
                              </svg>
                              Choose File
                            </label>
                            <span className="selected-file-name">
                              {selectedFile ? selectedFile.name : "No file chosen"}
                            </span>
                          </div>
                          <input
                            id="project-file-input"
                            key={fileInputKey}
                            className="sr-only"
                            type="file"
                            disabled={isUploading}
                            onChange={handleFileChange}
                          />
                        </div>
                        <div className="file-helper-strip">
                          <span>
                            <svg viewBox="0 0 24 24" aria-hidden="true">
                              <circle cx="12" cy="12" r="10" />
                              <path d="M12 16v-4" />
                              <path d="M12 8h.01" />
                            </svg>
                            Supported formats: PDF, DOCX, PPTX, XLSX, TXT, CSV, ZIP,
                            MP4, MP3, M4A, PNG, JPG, JPEG
                          </span>
                          <span>Max file size: 250MB</span>
                        </div>
                      </div>
                    </div>

                    <div className="form-actions upload-actions">
                      <button
                        type="submit"
                        className="primary-button upload-submit-button"
                        disabled={isUploading || !selectedFile}
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path d="M12 16V4" />
                          <path d="m7 9 5-5 5 5" />
                          <path d="M20 16v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4" />
                        </svg>
                        {isUploading ? "Uploading..." : "Upload File"}
                      </button>
                    </div>
                  </form>

                  {fileMessage ? (
                    <p
                      className={`upload-status-alert${
                        fileMessage.toLowerCase().includes("unable")
                          ? " upload-status-alert-error"
                          : ""
                      }`}
                    >
                      {fileMessage}
                    </p>
                  ) : null}

                  <section
                    className="recent-files-card"
                    aria-labelledby="recent-uploaded-files-title"
                  >
                    <div className="recent-files-header">
                      <span className="recent-files-header-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24">
                          <path d="M3.8 7.6V18c0 1.1.9 2 2 2h12.4c1.1 0 2-.9 2-2V8.8c0-1.1-.9-2-2-2h-6.1L10 4.6H5.8c-1.1 0-2 .9-2 2v1Z" />
                          <path d="M3.8 9.2h16.4" />
                        </svg>
                      </span>
                      <div>
                        <h3 id="recent-uploaded-files-title">Recent Uploaded Files</h3>
                        <p>Your uploaded files will appear here</p>
                      </div>
                      <button
                        type="button"
                        className="recent-files-refresh-button"
                        onClick={() => refreshFiles(params.projectId)}
                        disabled={isLoadingFiles}
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path d="M20 7v5h-5" />
                          <path d="M4 17v-5h5" />
                          <path d="M18.3 9A7 7 0 0 0 6.6 6.7L4 9" />
                          <path d="M5.7 15A7 7 0 0 0 17.4 17.3L20 15" />
                        </svg>
                        Refresh
                      </button>
                    </div>

                    {isLoadingFiles ? (
                      <p className="recent-files-loading">Loading uploaded files...</p>
                    ) : null}

                    {!isLoadingFiles && visibleUploadedFiles.length === 0 ? (
                      <div className="recent-files-empty">
                        <span className="empty-file-illustration" aria-hidden="true">
                          <svg viewBox="0 0 96 72">
                            <path d="M14 22h25l7 8h36v30a6 6 0 0 1-6 6H20a6 6 0 0 1-6-6Z" />
                            <path d="M32 8h32l8 8v26H32Z" />
                            <path d="M64 8v8h8" />
                            <path d="M41 25h22" />
                            <path d="M41 34h16" />
                          </svg>
                        </span>
                        <div>
                          <p>No files uploaded yet.</p>
                          <span>
                            Uploaded files will appear here after you add project source documents.
                          </span>
                        </div>
                      </div>
                    ) : null}

                    {!isLoadingFiles && visibleUploadedFiles.length > 0 ? (
                      <div className="recent-files-table">
                        <div className="recent-files-table-header" aria-hidden="true">
                          <span>File Name</span>
                          <span>Source Role</span>
                          <span>File Type</span>
                          <span>Uploaded</span>
                          <span />
                        </div>

                        <div className="recent-file-list">
                          {visibleUploadedFiles.map((uploadedFile) => {
                            const isPending = isPendingUploadedFile(uploadedFile);
                            const isDeleting = deletingUploadedFileIds.has(
                              uploadedFile.id,
                            );
                            const fileTypeVariant = getFileTypeVariant(
                              uploadedFile.file_type,
                            );
                            const sourceRoleVariant = getSourceRoleVariant(
                              uploadedFile.source_role,
                            );
                            const fileExtension = getUploadedFileExtension(uploadedFile);
                            const formattedUploadDate = formatProjectDate(
                              uploadedFile.created_at,
                            );
                            const uploadedDateParts =
                              splitFormattedDateTime(formattedUploadDate);
                            const isMenuOpen =
                              openFileActionMenuId === uploadedFile.id;

                            return (
                              <article
                                key={uploadedFile.id}
                                className={`recent-file-row${
                                  isPending ? " recent-file-row-pending" : ""
                                }`}
                              >
                                <div className="recent-file-cell recent-file-name-cell">
                                  <span
                                    className={`recent-file-icon recent-file-icon-${fileTypeVariant}`}
                                    aria-hidden="true"
                                  >
                                    <svg viewBox="0 0 24 24">
                                      <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7Z" />
                                      <path d="M14 2v5h5" />
                                    </svg>
                                    <span>{fileExtension}</span>
                                  </span>
                                  <div className="recent-file-name-copy">
                                    <h3 title={uploadedFile.original_filename}>
                                      {uploadedFile.original_filename}
                                    </h3>
                                    <p
                                      title={
                                        isPending
                                          ? "Upload in progress..."
                                          : uploadedFile.storage_path
                                      }
                                    >
                                      {isPending
                                        ? "Upload in progress..."
                                        : uploadedFile.storage_path || "Stored locally"}
                                    </p>
                                  </div>
                                </div>

                                <div className="recent-file-cell recent-file-role-cell">
                                  <span
                                    className={`source-role-accent source-role-accent-${sourceRoleVariant}`}
                                    aria-hidden="true"
                                  />
                                  <span
                                    className={`source-role-icon source-role-icon-${sourceRoleVariant}`}
                                    aria-hidden="true"
                                  >
                                    <svg viewBox="0 0 24 24">
                                      {sourceRoleVariant === "data" ? (
                                        <>
                                          <ellipse cx="12" cy="6" rx="5" ry="2.4" />
                                          <path d="M7 6v8c0 1.3 2.2 2.4 5 2.4s5-1.1 5-2.4V6" />
                                          <path d="M7 10c0 1.3 2.2 2.4 5 2.4s5-1.1 5-2.4" />
                                        </>
                                      ) : sourceRoleVariant === "technical" ? (
                                        <>
                                          <path d="M12 5v5" />
                                          <path d="M8 19v-4h8v4" />
                                          <path d="M6 19h4M14 19h4" />
                                          <path d="M9.5 10h5" />
                                          <path d="M12 10v5" />
                                        </>
                                      ) : (
                                        <>
                                          <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7Z" />
                                          <path d="M14 2v5h5" />
                                          <path d="M9 14h6" />
                                        </>
                                      )}
                                    </svg>
                                  </span>
                                  <span className="recent-file-role-label">
                                    {formatSourceRole(uploadedFile.source_role)}
                                  </span>
                                </div>

                                <div className="recent-file-cell">
                                  <span
                                    className={`file-type-badge file-type-badge-${fileTypeVariant}`}
                                  >
                                    {fileExtension}
                                  </span>
                                </div>

                                <div className="recent-file-cell recent-file-date-cell">
                                  <Icon name="calendar" className="recent-file-date-icon" />
                                  <span>
                                    <strong>{uploadedDateParts.date}</strong>
                                    {uploadedDateParts.time ? (
                                      <small>{uploadedDateParts.time}</small>
                                    ) : null}
                                  </span>
                                </div>

                                <div className="recent-file-cell recent-file-actions">
                                  {!isPending ? (
                                    <>
                                      <button
                                        type="button"
                                        className="file-actions-button"
                                        aria-label={`Open actions for ${uploadedFile.original_filename}`}
                                        aria-haspopup="menu"
                                        aria-expanded={isMenuOpen}
                                        onClick={() =>
                                          setOpenFileActionMenuId((current) =>
                                            current === uploadedFile.id
                                              ? null
                                              : uploadedFile.id,
                                          )
                                        }
                                      >
                                        <svg viewBox="0 0 24 24" aria-hidden="true">
                                          <path d="M12 6.5h.01" />
                                          <path d="M12 12h.01" />
                                          <path d="M12 17.5h.01" />
                                        </svg>
                                      </button>

                                      {isMenuOpen ? (
                                        <div className="file-actions-menu" role="menu">
                                          <button
                                            type="button"
                                            role="menuitem"
                                            disabled={isDeleting}
                                            onClick={() => {
                                              setOpenFileActionMenuId(null);
                                              void handleDeleteUploadedFile(uploadedFile);
                                            }}
                                          >
                                            <svg viewBox="0 0 24 24" aria-hidden="true">
                                              <path d="M4 7h16" />
                                              <path d="M10 11v6" />
                                              <path d="M14 11v6" />
                                              <path d="M6 7l1 14h10l1-14" />
                                              <path d="M9 7V4h6v3" />
                                            </svg>
                                            {isDeleting ? "Removing..." : "Remove"}
                                          </button>
                                        </div>
                                      ) : null}
                                    </>
                                  ) : null}
                                </div>
                              </article>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}
                  </section>
                </div>
              ) : null}
            </section>

            <div className="debug-optional-group" aria-labelledby="debug-optional-title">
              <div className="debug-optional-header">
                <span className="debug-optional-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <path d="M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5Z" />
                    <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3a2 2 0 1 1 4 0v.1A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.23.38.6.74 1 .9.35.13.72.2 1.1.2h.1a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.1.4c-.4.3-.73.65-1 1Z" />
                  </svg>
                </span>
                <div>
                  <h2 id="debug-optional-title">Debug / Optional</h2>
                  <p className="muted-text">
                    Developer tools and advanced review sections.
                  </p>
                </div>
              </div>

            <section
              className="panel optional-section-card optional-section-jobs"
              aria-labelledby="jobs-title"
            >
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

            <section
              className="panel optional-section-card optional-section-aud-plan"
              aria-labelledby="aud-plan-title"
            >
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

            <section
              className="panel optional-section-card optional-section-open-points"
              aria-labelledby="open-points-title"
            >
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

            <section
              className="panel optional-section-card optional-section-source-priority"
              aria-labelledby="source-priority-title"
            >
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

            <section
              className="panel optional-section-card optional-section-evidence-index"
              aria-labelledby="evidence-index-title"
            >
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

            <section
              className="panel optional-section-card optional-section-source-summaries"
              aria-labelledby="source-summaries-title"
            >
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

            <section
              className="panel optional-section-card optional-section-section-drafts"
              aria-labelledby="section-drafts-title"
            >
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

            <section
              className="panel optional-section-card optional-section-extracted-content"
              aria-labelledby="extracted-content-title"
            >
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

            <section
              className="panel optional-section-card optional-section-generated-documents"
              aria-labelledby="generated-documents-title"
            >
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
            </div>
          </>
        ) : null}
      </section>
      <AudGenerationProgressModal
        isOpen={isAudProgressModalOpen}
        onClose={() => setIsAudProgressModalOpen(false)}
        audGenerationStatus={audGenerationStatus}
        isLoadingAudGenerationStatus={isLoadingAudGenerationStatus}
        audGenerationMessage={audGenerationMessage}
      />
    </main>
  );
}
