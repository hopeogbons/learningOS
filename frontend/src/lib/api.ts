"use client";
import { useCallback, useEffect, useState } from "react";
import type { components } from "./api.generated";

export type Profile = components["schemas"]["LearnerDTO"];
export type ScopeProgress = {
  completed_count: number;
  total_in_scope: number;
  percent: number;
  review_needed_count: number;
};
export type Scope = components["schemas"]["ScopeDTO"];
export type Collection = components["schemas"]["CollectionDTO"];
export type Material = components["schemas"]["MaterialDTO"] & {
  chunks?: Chunk[];
  drive_file_id?: string | null;
};
export type Chunk = components["schemas"]["ChunkDTO"] & {
  concept_count?: number;
};
export type Outline = components["schemas"]["OutlineDTO"];
export type Calibration =
  components["schemas"]["app__core_schemas__CalibrationDTO"];
export type ReviewItem = {
  chunk_id: string;
  title: string;
  collection_id: string;
  stage: number;
  next_review_at: string;
  needs_attention: boolean;
  source?: string;
};
export type Dashboard = {
  learner: Profile;
  collections_count: number;
  due_count: number;
  collections: Collection[];
  scope_progress: ScopeProgress;
  resume: {
    session_id?: string;
    id?: string;
    title?: string;
    collection_id?: string;
    scope_revision_id?: string;
  } | null;
  calibration: Calibration;
  recent_materials: Material[];
  connections: Connection[];
  mode: string;
  demo_notice?: string;
};
export type Connection = {
  provider: string;
  status: string;
  configured?: boolean;
  scopes?: string[];
  error?: string;
  connected?: boolean;
  last_sync_at?: string | null;
};
export type Job = {
  id: string;
  status: string;
  error?: string | null;
  error_code?: string | null;
  result?: Record<string, unknown>;
  storage_state?: string;
};
export type Citation = components["schemas"]["CitationDTO"];
export type Session = {
  id: string;
  status: string;
  version: number;
  collection_id: string;
  scope_revision_id: string;
  mode: string;
  job_id?: string;
  demo?: boolean;
};
export type Reviewer = {
  correct?: boolean;
  correctness?: string | boolean;
  feedback?: string;
  rationale?: string;
  missing_parts?: string[];
  wrong_parts?: string[];
  title_completed?: boolean;
  title_complete?: boolean;
  citation_ids?: string[];
  decision?: string;
  uncertainty?: string;
  [key: string]: unknown;
};
export type SessionItem = {
  session_id: string;
  item_id: string | null;
  version: number;
  status: string;
  question?: string;
  teaching?: string;
  citation_ids: string[];
  concept_id?: string;
  chunk_id?: string;
  generation_locale?: string;
  feedback?: Reviewer | null;
  job_id?: string;
  job_state?: string;
  error_code?: string;
  retryable?: boolean;
  voice_turn_count?: number;
};
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (options.method && !["GET", "HEAD"].includes(options.method)) {
    headers.set(
      "Idempotency-Key",
      headers.get("Idempotency-Key") ?? crypto.randomUUID(),
    );
    const csrf = document.cookie
      .split("; ")
      .find((c) => c.startsWith("learningos_csrf="))
      ?.split("=")
      .slice(1)
      .join("=");
    if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...options,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      0,
      "Unable to reach Learning OS. Check your connection and retry.",
      "network_unavailable",
    );
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error ?? body?.detail;
    throw new ApiError(
      response.status,
      typeof error === "string"
        ? error
        : (error?.message ?? `Request failed (${response.status})`),
      error?.code,
    );
  }
  if (path === "/dashboard" && Array.isArray(body?.scope_progress)) {
    const scoped = body.scope_progress;
    body.scope_progress =
      scoped.find(
        (p: { collection_id: string }) =>
          p.collection_id === body.resume?.collection_id,
      ) ??
      scoped.find((p: { total_in_scope: number }) => p.total_in_scope > 0) ??
      emptyProgress;
  }
  return body as T;
}
export function useApi<T>(path: string | null) {
  const [data, updateData] = useState<T | null>(null),
    [loadedPath, setLoadedPath] = useState<string | null>(null),
    [error, setError] = useState<string | null>(null),
    [loading, setLoading] = useState(Boolean(path)),
    [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((n) => n + 1), []);
  useEffect(() => {
    let active = true;
    if (!path) return;
    api<T>(path)
      .then((value) => {
        if (active) {
          updateData(value);
          setLoadedPath(path);
          setError(null);
        }
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          setLoadedPath(path);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, revision]);
  const setData = useCallback(
    (value: T | null) => {
      updateData(value);
      setLoadedPath(path);
    },
    [path],
  );
  return {
    data: loadedPath === path ? data : null,
    error: loadedPath === path ? error : null,
    loading: Boolean(path) && (loading || loadedPath !== path),
    reload,
    setData,
  };
}
export const json = (body: unknown) => JSON.stringify(body);
export const emptyProgress: ScopeProgress = {
  completed_count: 0,
  total_in_scope: 0,
  percent: 0,
  review_needed_count: 0,
};
export function list<T>(data: { items: T[] } | T[] | null | undefined): T[] {
  return Array.isArray(data) ? data : (data?.items ?? []);
}
export async function apiBlob(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<Blob> {
  const headers = new Headers({
    "Content-Type": "application/json",
    "Idempotency-Key": crypto.randomUUID(),
  });
  const csrf = document.cookie
    .split("; ")
    .find((c) => c.startsWith("learningos_csrf="))
    ?.split("=")
    .slice(1)
    .join("=");
  if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  const response = await fetch(`/api/v1${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    credentials: "same-origin",
    signal,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      data.error?.message ??
        data.detail?.message ??
        "Speech service unavailable",
    );
  }
  return response.blob();
}

export type PageResult<T> = {
  items: T[];
  total: number;
  next_cursor: number | null;
};
/** Explicit pagination keeps reads bounded while allowing every owned row to be reached. */
export function usePagedApi<T>(path: string | null) {
  const query = useApi<PageResult<T>>(path);
  const [moreLoading, setMoreLoading] = useState(false);
  const [moreError, setMoreError] = useState<string | null>(null);
  const loadMore = async () => {
    if (!path || query.data?.next_cursor == null || moreLoading) return;
    setMoreLoading(true);
    setMoreError(null);
    try {
      const separator = path.includes("?") ? "&" : "?";
      const next = await api<PageResult<T>>(
        `${path}${separator}cursor=${query.data.next_cursor}`,
      );
      query.setData({ ...next, items: [...query.data.items, ...next.items] });
    } catch (error) {
      setMoreError((error as Error).message);
    } finally {
      setMoreLoading(false);
    }
  };
  return {
    ...query,
    error: moreError ?? query.error,
    loadMore,
    moreLoading,
    hasMore: query.data?.next_cursor != null,
  };
}
