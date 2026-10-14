"use client";
import Link from "next/link";
import { useI18n } from "@/i18n";
import { friendlyErrorKey } from "@/lib/errors";
import type { Citation, Collection } from "@/lib/api";
export function Card({
  children,
  className = "",
  ...props
}: {
  children: React.ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section
      className={`card border-0 shadow-sm rounded-4 ${className}`}
      {...props}
    >
      <div className="card-body p-3 p-lg-4">{children}</div>
    </section>
  );
}
export function PageTitle({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="route-heading mb-4">
      <h1 className="h3 fw-bold mb-2">{title}</h1>
      {description && <p className="text-body-secondary mb-0">{description}</p>}
    </div>
  );
}
export function Status({
  error,
  loading,
  retry,
}: {
  error?: string | null;
  loading?: boolean;
  retry?: () => void;
}) {
  const { t } = useI18n();
  if (error === "authentication_required" || error === "authentication required")
    return (
      <div role="alert" className="alert alert-primary">
        <p className="mb-2">{t("auth.required")}</p>
        <a href="/api/v1/auth/login" className="btn btn-primary btn-sm">
          {t("auth.signIn")}
        </a>
      </div>
    );
  if (error)
    return (
      <div role="alert" className="alert alert-danger">
        <p className="mb-2">{t("common.error")}</p>
        <p className="small mb-2">{t(friendlyErrorKey(error))}</p>
        {retry && (
          <button className="btn btn-outline-danger btn-sm" onClick={retry}>
            {t("common.retry")}
          </button>
        )}
      </div>
    );
  if (loading)
    return (
      <div
        role="status"
        aria-live="polite"
        className="skeleton card border-0 rounded-4 p-4"
      >
        <span className="visually-hidden">{t("common.loading")}</span>
        <span />
        <span />
        <span />
      </div>
    );
  return null;
}
export function Empty({
  children,
  href,
  label,
}: {
  children: React.ReactNode;
  href?: string;
  label?: string;
}) {
  return (
    <div className="empty-state text-body-secondary py-4 text-center">
      <p className="mb-2">{children}</p>
      {href && (
        <Link href={href} className="btn btn-outline-primary btn-sm">
          {label}
        </Link>
      )}
    </div>
  );
}
export function CollectionPicker({
  items,
  value,
  onChange,
  hasMore = false,
  onLoadMore,
  moreLoading = false,
}: {
  items: Collection[];
  value: string;
  onChange: (id: string) => void;
  hasMore?: boolean;
  onLoadMore?: () => void;
  moreLoading?: boolean;
}) {
  const { t } = useI18n();
  return (
    <div className="mb-3">
      <label className="d-block">
        <span className="form-label fw-semibold small">
          {t("outline.chooseCollection")}
        </span>
        <select
          className="form-select"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">{t("outline.chooseCollection")}</option>
          {items.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      {hasMore && (
        <button
          type="button"
          className="btn btn-light border btn-sm mt-2"
          onClick={onLoadMore}
          disabled={moreLoading}
        >
          {t(moreLoading ? "common.loading" : "common.continue")}
        </button>
      )}
    </div>
  );
}
export function StorageBadge({ state }: { state: string }) {
  const { t } = useI18n();
  const keys: Record<string, string> = {
    local: "common.local",
    ready: "common.ready",
    drive_ready: "common.ready",
    saved_to_drive: "common.savedToDrive",
    provisioning: "common.provisioning",
    connecting: "common.connecting",
    upload_pending: "common.uploadPending",
    uploading: "common.uploading",
    failed: "common.failed",
    cancelled: "common.cancelled",
    attention: "common.attention",
    needs_attention: "common.attention",
    pending: "common.uploadPending",
    disconnected: "common.disconnected",
    queued: "common.queued",
    running: "common.processing",
    processing: "common.processing",
    succeeded: "common.ready",
  };
  return (
    <span
      className={`badge rounded-pill text-bg-light border fw-medium ${state === "failed" ? "text-danger" : ""}`}
    >
      {t(
        keys[state.replaceAll("-", "_")] ??
          (state === "local-only" ? "common.local" : "common.unknown"),
      )}
    </span>
  );
}
export function CitationList({ citations }: { citations: Citation[] }) {
  const { t } = useI18n();
  return (
    <aside className="citation-list mt-3" aria-label={t("study.evidence")}>
      {citations.map((c) => {
        const locator =
          typeof c.locator === "string"
            ? c.locator
            : Object.entries(c.locator ?? {})
                .filter(([k]) => k !== "url")
                .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join("–") : v}`)
                .join(" · ");
        return (
          <details key={c.id} className="citation-chip">
            <summary>
              <bdi>
                {c.source_title ?? c.id} {locator}
              </bdi>
            </summary>
            <blockquote className="mb-0 mt-2 small" dir="auto">
              {c.excerpt}
            </blockquote>
            {c.viewer_url &&
              /^\/api\/v1\/material-revisions\/[a-zA-Z0-9-]+\/original$/.test(
                c.viewer_url,
              ) && (
                <a
                  href={c.viewer_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t("upload.original")}
                </a>
              )}
            {c.source_url && /^https?:\/\//.test(c.source_url ?? "") && (
              <a href={c.source_url} rel="noopener noreferrer" target="_blank">
                {t("upload.original")}
              </a>
            )}
          </details>
        );
      })}
    </aside>
  );
}
