"use client";
import { useState } from "react";
import Link from "next/link";
import { Plus, Edit3, Cloud } from "lucide-react";
import { useI18n } from "@/i18n";
import { api, json, list, useApi, usePagedApi, type Collection, type Connection } from "@/lib/api";
import { useApp } from "../AppState";
import { Card, PageTitle, Status, Empty } from "../Shared";
import { CollectionRow } from "../DesktopPanels";
export default function CollectionsScreen() {
  const { t, locale } = useI18n(),
    { reload: refresh } = useApp(),
    query = usePagedApi<Collection>("/collections"),
    connections = useApi<Connection[]>("/connections"),
    [editing, setEditing] = useState<Collection | null>(null),
    [storageChoice, setStorageChoice] = useState<string | null>(null),
    [form, setForm] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null);
  const items = list(query.data);
  const driveReady = list(connections.data).some(
    (connection) => connection.provider === "drive" &&
      connection.status === "connected" && connection.configured === true,
  );
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const f = new FormData(e.currentTarget);
    try {
      await api(editing ? `/collections/${editing.id}` : "/collections", {
        method: editing ? "PATCH" : "POST",
        body: json({
          name: f.get("name"),
          note: f.get("note"),
          ...(editing
            ? { expected_version: editing.version }
            : {
                storage_mode: f.get("storage_mode"),
                icon_key: "folder",
                color_key: ["blue", "teal", "purple"][items.length % 3],
              }),
        }),
      });
      setForm(false);
      setEditing(null);
      query.reload();
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        title={t("collection.title")}
        description={t("collection.description")}
      />
      <div className="mb-4">
        <button
          className="btn btn-primary d-inline-flex align-items-center gap-2"
          onClick={() => {
            setEditing(null);
            setStorageChoice(null);
            setForm(!form);
          }}
        >
          <Plus size={18} />
          {t("collection.create")}
        </button>
      </div>
      <Status
        loading={query.loading}
        error={query.error}
        retry={query.reload}
      />
      {form && (
        <Card className="mb-4">
          <h2 className="h5 fw-bold">
            {t(editing ? "collection.rename" : "collection.create")}
          </h2>
          <form key={editing?.id ?? "new"} onSubmit={save}>
            <label className="d-block mb-3">
              <span className="form-label">{t("collection.name")}</span>
              <input
                name="name"
                required
                maxLength={120}
                className="form-control"
                defaultValue={editing?.name ?? ""}
                dir="auto"
              />
            </label>
            <label className="d-block mb-3">
              <span className="form-label">{t("collection.note")}</span>
              <input
                name="note"
                maxLength={500}
                className="form-control"
                defaultValue={editing?.note ?? ""}
                dir="auto"
              />
            </label>
            <label className="d-block mb-3">
              <span className="form-label">{t("collection.destination")}</span>
              <select
                name="storage_mode"
                className="form-select"
                value={editing?.storage_mode ?? storageChoice ?? (driveReady ? "drive" : "local")}
                onChange={(event) => setStorageChoice(event.target.value)}
                disabled={Boolean(editing)}
              >
                <option value="local">{t("common.local")}</option>
                <option value="drive" disabled={!driveReady}>{t("common.drive")}</option>
              </select>
            </label>
            <p className="small text-body-secondary">
              {t("collection.driveDescription")}
            </p>
            <Status error={error} />
            <div className="d-flex gap-2">
              <button className="btn btn-primary" disabled={busy || (!editing && connections.loading)}>
                {t(busy ? "common.working" : "common.save")}
              </button>
              <button
                type="button"
                className="btn btn-light"
                onClick={() => setForm(false)}
              >
                {t("common.cancel")}
              </button>
            </div>
          </form>
        </Card>
      )}
      <div className="d-flex flex-column gap-3">
        {items.map((c) => (
          <Card key={c.id}>
            <CollectionRow collection={c} />
            <div className="d-flex flex-wrap gap-2 mt-3">
              <Link
                href={`/collections/${c.id}/outline`}
                className="btn btn-outline-primary btn-sm"
              >
                {t("collection.openOutline")}
              </Link>
              <Link
                href={`/add-material?collection=${c.id}`}
                className="btn btn-light border btn-sm"
              >
                {t("collection.add")}
              </Link>
              <button
                className="btn btn-light border btn-sm d-inline-flex gap-1 align-items-center"
                onClick={() => {
                  setEditing(c);
                  setForm(true);
                }}
              >
                <Edit3 size={14} />
                {t("common.edit")}
              </button>
            </div>
            {c.storage_mode === "drive" && (
              <div className="small text-body-secondary mt-3">
                <Cloud size={14} className="me-1" />
                {t("collection.folder")}:{" "}
                <bdi>{c.drive_folder_id ?? t("common.notAvailable")}</bdi>
                <div>
                  {t("collection.lastSync")}:{" "}
                  {c.last_sync_at
                    ? new Date(c.last_sync_at).toLocaleString(locale)
                    : t("collection.noSync")}
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>
      {query.hasMore && (
        <button
          className="btn btn-light border btn-sm mt-3"
          disabled={query.moreLoading}
          onClick={query.loadMore}
        >
          {t(query.moreLoading ? "common.loading" : "common.continue")}
        </button>
      )}
      {!query.loading && !items.length && (
        <Card>
          <Empty>{t("home.noCollections")}</Empty>
        </Card>
      )}
    </>
  );
}
