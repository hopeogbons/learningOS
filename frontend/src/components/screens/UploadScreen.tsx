"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { FilePlus2, Camera, Link2, Sheet } from "lucide-react";
import { useI18n } from "@/i18n";
import {
  api,
  json,
  list,
  useApi,
  usePagedApi,
  type Collection,
  type Job,
  type Material,
} from "@/lib/api";
import { friendlyErrorKey } from "@/lib/errors";
import { useApp } from "../AppState";
import {
  Card,
  PageTitle,
  CollectionPicker,
  Status,
  StorageBadge,
  Empty,
} from "../Shared";
type Receipt = {
  material_id: string;
  revision_id: string;
  job_id: string;
  status: string;
  storage_state: string;
  drive_file_id?: string | null;
};
const TERMINAL_JOBS = ["succeeded", "failed", "needs_attention", "needs-attention", "cancelled"];
export default function UploadScreen({
  initialCollection = "",
}: {
  initialCollection?: string;
}) {
  const { t } = useI18n(),
    { reload } = useApp(),
    [collectionId, setCollection] = useState(initialCollection),
    [tab, setTab] = useState("file"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null),
    [notice, setNotice] = useState(false),
    [receipts, setReceipts] = useState<Receipt[]>([]),
    [jobStatuses, setJobStatuses] = useState<Record<string, string>>({}),
    collections = usePagedApi<Collection>("/collections"),
    materials = usePagedApi<Material>(
      collectionId ? `/collections/${collectionId}/materials` : null,
    ),
    intakeKey = useRef<string | null>(null);
  const selected = list(collections.data).find((c) => c.id === collectionId);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!collectionId) return;
    setBusy(true);
    setError(null);
    setNotice(false);
    const form = e.currentTarget;
    try {
      const payload = new FormData(form);
      const key =
        intakeKey.current ?? (intakeKey.current = crypto.randomUUID());
      let receipt: Receipt;
      if (tab === "link")
        receipt = await api(`/collections/${collectionId}/link`, {
          method: "POST",
          body: json({
            url: payload.get("url"),
            idempotency_key: key,
            source_language: payload.get("source_language"),
          }),
        });
      else {
        const file = payload.get("file") as File;
        if (!file?.size) throw new Error(t("upload.selectFile"));
        if (file.size > 20 * 1024 * 1024) throw new Error(t("upload.accepted"));
        payload.set("idempotency_key", key);
        receipt = await api(`/collections/${collectionId}/materials`, {
          method: "POST",
          body: payload,
        });
      }
      setReceipts((r) => [receipt, ...r]);
      intakeKey.current = null;
      setNotice(true);
      form.reset();
      materials.reload();
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const refreshMaterials = materials.reload;
  const onJobStatus = useCallback((jobId: string, status: string) => {
    setJobStatuses((previous) => previous[jobId] === status
      ? previous
      : { ...previous, [jobId]: status });
    if (TERMINAL_JOBS.includes(status)) {
      refreshMaterials();
      reload();
    }
  }, [refreshMaterials, reload]);
  const pendingReceipts = receipts.some(
    (receipt) => !TERMINAL_JOBS.includes(jobStatuses[receipt.job_id] ?? receipt.status),
  );
  useEffect(() => {
    if (!pendingReceipts) return;
    const poll = setInterval(() => {
      refreshMaterials();
      reload();
    }, 2500);
    return () => clearInterval(poll);
  }, [pendingReceipts, refreshMaterials, reload]);
  return (
    <>
      <PageTitle
        title={t("upload.title")}
        description={t("upload.description")}
      />
      <Card>
        <CollectionPicker
          hasMore={collections.hasMore}
          onLoadMore={collections.loadMore}
          moreLoading={collections.moreLoading}
          items={list(collections.data)}
          value={collectionId}
          onChange={(id) => {
            setCollection(id);
            intakeKey.current = null;
            setReceipts([]);
            setNotice(false);
          }}
        />
        <Status
          error={collections.error}
          loading={collections.loading}
          retry={collections.reload}
        />
        {selected && (
          <div className="destination-note mb-3 p-3 rounded-3 bg-body-tertiary">
            <strong className="small">
              {t("upload.destination")}: <bdi>{selected.name}</bdi>
            </strong>{" "}
            <StorageBadge
              state={
                selected.storage_mode === "drive" &&
                selected.provisioning_state === "ready"
                  ? "drive_ready"
                  : selected.storage_mode === "drive"
                    ? selected.provisioning_state
                    : "local"
              }
            />
            <p className="small text-body-secondary mb-0 mt-2">
              {t(
                selected.storage_mode === "drive"
                  ? "upload.driveWarning"
                  : "upload.localWarning",
              )}
            </p>
            {selected.storage_mode === "drive" && (
              <p className="small mb-0">
                <bdi>
                  {selected.drive_folder_id ?? t("common.provisioning")}
                </bdi>
              </p>
            )}
          </div>
        )}
        <div className="nav nav-pills gap-2 mb-4" role="tablist">
          {[
            { id: "file", key: "upload.file", icon: FilePlus2 },
            { id: "photo", key: "upload.photo", icon: Camera },
            { id: "spreadsheet", key: "upload.spreadsheet", icon: Sheet },
            { id: "link", key: "upload.link", icon: Link2 },
          ].map(({ id, key, icon: Icon }) => (
            <button
              key={id}
              type="button"
              className={`nav-link d-flex align-items-center gap-2${tab === id ? " active" : ""}`}
              role="tab"
              aria-selected={tab === id}
              aria-controls="upload-panel"
              onClick={() => {
                setTab(id);
                setError(null);
              }}
            >
              <Icon size={18} />
              {t(key)}
            </button>
          ))}
        </div>
        <form key={tab} id="upload-panel" role="tabpanel" onSubmit={submit}>
          {tab === "link" ? (
            <label className="d-block mb-3">
              <span className="form-label fw-semibold">{t("upload.url")}</span>
              <input
                type="url"
                name="url"
                onChange={() => {
                  intakeKey.current = null;
                }}
                required
                className="form-control"
                placeholder="https://"
                dir="ltr"
              />
              <small className="text-body-secondary d-block mt-2">
                {t("upload.linkHelp")}
              </small>
            </label>
          ) : (
            <label className="upload-dropzone d-block mb-3">
              <span className="d-block fw-semibold mb-3">
                {t(tab === "photo" ? "upload.capture" : "upload.selectFile")}
              </span>
              <input
                name="file"
                type="file"
                onChange={() => {
                  intakeKey.current = null;
                }}
                required
                className="form-control"
                accept={
                  tab === "photo"
                    ? "image/jpeg,image/png"
                    : tab === "spreadsheet"
                      ? ".csv,.xlsx"
                      : ".pdf,.md,.txt,.csv,.xlsx,.jpg,.jpeg,.png"
                }
                {...(tab === "photo"
                  ? { capture: "environment" as const }
                  : {})}
              />
              <small className="d-block text-body-secondary mt-3">
                {t(tab === "photo" ? "upload.photoHelp" : "upload.accepted")}
              </small>
            </label>
          )}
          <SourceLanguageSelect
            onChange={() => {
              intakeKey.current = null;
            }}
          />
          <p className="small text-body-secondary">
            {t("upload.sourceLanguageHelp")}
          </p>
          <Status error={error} />
          {notice && (
            <div role="status" className="alert alert-success">
              {t("upload.success")}
            </div>
          )}
          <button
            className="btn btn-success d-inline-flex align-items-center gap-2"
            disabled={busy || !collectionId}
          >
            <FilePlus2 size={18} />
            {t(busy ? "common.working" : "upload.submit")}
          </button>
        </form>
      </Card>
      <Card className="mt-4">
        <h2 className="h5 fw-bold mb-3">{t("upload.jobs")}</h2>
        {receipts.map((r) => (
          <JobRow key={r.job_id} receipt={r} onStatus={onJobStatus} />
        ))}
        <Status
          error={materials.error}
          loading={Boolean(collectionId) && materials.loading}
          retry={materials.reload}
        />
        {list(materials.data).map((m) => (
          <div
            key={m.id}
            className="event-row py-3 d-flex align-items-center flex-wrap gap-2"
          >
            <span className="fw-medium flex-grow-1">
              <bdi>{m.title}</bdi>
            </span>
            <StorageBadge state={m.storage_state ?? "local"} />
            <StorageBadge state={m.status} />
            {m.current_revision_id && (
              <MaterialLanguage
                key={`${m.id}:${m.source_language}`}
                material={m}
                onSaved={materials.reload}
              />
            )}
          </div>
        ))}
        {materials.hasMore && (
          <button
            className="btn btn-light border btn-sm mt-3"
            disabled={materials.moreLoading}
            onClick={materials.loadMore}
          >
            {t(materials.moreLoading ? "common.loading" : "common.continue")}
          </button>
        )}
        {!receipts.length && !list(materials.data).length && (
          <Empty>{t("upload.noJobs")}</Empty>
        )}
      </Card>
    </>
  );
}
function JobRow({ receipt: r, onStatus }: {
  receipt: Receipt;
  onStatus: (jobId: string, status: string) => void;
}) {
  const { t } = useI18n(),
    query = useApi<Job>(`/jobs/${r.job_id}`),
    [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (
      query.data &&
      TERMINAL_JOBS.includes(
        query.data.status,
      )
    )
      return;
    const interval = setInterval(query.reload, 1200);
    return () => clearInterval(interval);
  }, [query.data, query.reload]);
  useEffect(() => {
    if (query.data?.status) onStatus(r.job_id, query.data.status);
  }, [query.data?.status, r.job_id, onStatus]);
  const storageState = typeof query.data?.result?.storage_state === "string"
    ? query.data.result.storage_state
    : r.storage_state;
  return (
    <div className="event-row py-3">
      <div className="d-flex gap-2 align-items-center flex-wrap">
        <span className="small fw-semibold flex-grow-1">
          <bdi>{r.material_id}</bdi>
        </span>
        <StorageBadge state={storageState} />
        <StorageBadge state={query.data?.status ?? r.status} />
      </div>
      {r.drive_file_id && (
        <p className="small text-body-secondary mt-2 mb-0">
          {t("upload.driveReceipt")}: <bdi>{r.drive_file_id}</bdi>
        </p>
      )}
      {(query.data?.error || query.data?.error_code) && (
        <p className="small text-danger mt-2 mb-0" role="alert">
          <bdi>
            {t(
              friendlyErrorKey(query.data.error ?? query.data.error_code ?? ""),
            )}
          </bdi>
        </p>
      )}
      {query.data && ["failed", "needs_attention", "needs-attention"].includes(query.data.status) && (
        <button
          className="btn btn-outline-primary btn-sm mt-2"
          onClick={async () => {
            try {
              await api(`/jobs/${r.job_id}/retry`, { method: "POST" });
              query.reload();
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          {t("upload.retry")}
        </button>
      )}
      <Status error={error ?? query.error} />
    </div>
  );
}

function SourceLanguageSelect({
  value = "und",
  onChange,
}: {
  value?: string;
  onChange?: () => void;
}) {
  const { t, languages } = useI18n();
  return (
    <label className="d-block mb-3">
      <span className="form-label fw-semibold">
        {t("upload.sourceLanguage")}
      </span>
      <select
        className="form-select"
        name="source_language"
        defaultValue={value}
        onChange={onChange}
      >
        <option value="und">{t("upload.unknownLanguage")}</option>
        {value !== "und" &&
          !languages.some((language) => language.locale === value) && (
            <option value={value}>{value}</option>
          )}
        {languages.map((language) => (
          <option key={language.locale} value={language.locale}>
            {language.native}
          </option>
        ))}
      </select>
    </label>
  );
}

function MaterialLanguage({
  material,
  onSaved,
}: {
  material: Material;
  onSaved: () => void;
}) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source_language = new FormData(event.currentTarget).get(
      "source_language",
    );
    setBusy(true);
    setError(null);
    try {
      await api(`/materials/${material.id}/source-language`, {
        method: "PATCH",
        body: json({ source_language }),
      });
      onSaved();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save} className="w-100 mt-2">
      <SourceLanguageSelect value={material.source_language} />
      <button className="btn btn-outline-primary btn-sm" disabled={busy}>
        {t(busy ? "common.working" : "common.save")}
      </button>
      <Status error={error} />
    </form>
  );
}
