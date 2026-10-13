"use client";
import { useState } from "react";
import { Download, Trash2 } from "lucide-react";
import { useI18n, type Locale } from "@/i18n";
import { api, json, useApi, type Profile } from "@/lib/api";
import { useApp } from "../AppState";
import { Card, PageTitle, Status } from "../Shared";
export default function ProfileScreen() {
  const { t, preferences, setPreferences, languages } = useI18n(),
    { reload } = useApp(),
    query = useApi<Profile>("/me"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null),
    [saved, setSaved] = useState(false),
    [confirmDelete, setConfirmDelete] = useState(false),
    [deleted, setDeleted] = useState(false);
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    const f = new FormData(e.currentTarget);
    try {
      const p = await api<Profile>("/me", {
        method: "PATCH",
        body: json({
          display_name: f.get("display_name"),
          timezone: f.get("timezone"),
          ...preferences,
        }),
      });
      query.setData(p);
      reload();
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function exportData() {
    setBusy(true);
    setError(null);
    try {
      const data = await api("/me/export");
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "learning-os-my-data.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function erase(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (new FormData(e.currentTarget).get("confirmation") !== "DELETE") return;
    setBusy(true);
    setError(null);
    try {
      await api("/me", {
        method: "DELETE",
        body: json({ confirmation: "DELETE" }),
      });
      setDeleted(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle title={t("profile.title")} />
      <Status
        error={error ?? query.error}
        loading={query.loading}
        retry={query.reload}
      />
      {saved && (
        <p className="alert alert-success" role="status">
          {t("common.updated")}
        </p>
      )}
      {deleted ? (
        <Card>
          <p role="status">{t("common.processing")}</p>
        </Card>
      ) : (
        <>
          <Card className="mb-4">
            <form key={query.data?.id ?? "loading"} onSubmit={save}>
              <h2 className="h5 fw-bold mb-3">{t("profile.account")}</h2>
              <label className="d-block mb-3">
                <span className="form-label">{t("profile.name")}</span>
                <input
                  required
                  name="display_name"
                  maxLength={120}
                  className="form-control"
                  defaultValue={query.data?.display_name ?? ""}
                  dir="auto"
                />
              </label>
              <label className="d-block mb-4">
                <span className="form-label">{t("profile.timezone")}</span>
                <input
                  required
                  name="timezone"
                  className="form-control"
                  defaultValue={query.data?.timezone ?? "Africa/Lagos"}
                  dir="ltr"
                  placeholder="Africa/Lagos"
                />
              </label>
              <h2 className="h5 fw-bold mb-3">{t("profile.preferences")}</h2>
              {[
                { key: "profile.uiLanguage", field: "ui_locale" as const },
                {
                  key: "profile.studyLanguage",
                  field: "study_locale" as const,
                },
                {
                  key: "profile.speechLanguage",
                  field: "speech_locale" as const,
                },
              ].map(({ key, field }) => (
                <label key={field} className="d-block mb-3">
                  <span className="form-label">{t(key)}</span>
                  <select
                    className="form-select"
                    value={preferences[field]}
                    onChange={(e) =>
                      setPreferences({ [field]: e.target.value as Locale })
                    }
                  >
                    {languages.map((l) => (
                      <option
                        key={l.locale}
                        value={field === "speech_locale" ? l.speech : l.locale}
                      >
                        {l.native} ({l.english})
                      </option>
                    ))}
                  </select>
                </label>
              ))}
              <p className="small text-body-secondary">
                {t("profile.original")}
              </p>
              <button className="btn btn-primary" disabled={busy}>
                {t(busy ? "common.working" : "common.save")}
              </button>
            </form>
          </Card>
          <Card>
            <h2 className="h5 fw-bold mb-3">{t("profile.export")}</h2>
            <p className="small text-body-secondary">
              {t("profile.exportDescription")}
            </p>
            <button
              className="btn btn-outline-primary d-inline-flex align-items-center gap-2"
              disabled={busy}
              onClick={exportData}
            >
              <Download size={18} />
              {t("profile.export")}
            </button>
            <hr className="my-4" />
            <h2 className="h5 fw-bold">{t("profile.delete")}</h2>
            <p className="small text-body-secondary">
              {t("profile.deleteWarning")}
            </p>
            {!confirmDelete ? (
              <button
                className="btn btn-outline-danger d-flex align-items-center gap-2"
                onClick={() => setConfirmDelete(true)}
              >
                <Trash2 size={18} />
                {t("profile.delete")}
              </button>
            ) : (
              <form onSubmit={erase}>
                <label className="d-block mb-3">
                  <span className="form-label">
                    {t("profile.deleteConfirm")}
                  </span>
                  <input
                    name="confirmation"
                    required
                    pattern="DELETE"
                    className="form-control"
                    autoComplete="off"
                    dir="ltr"
                  />
                </label>
                <div className="d-flex gap-2">
                  <button className="btn btn-danger" disabled={busy}>
                    {t("common.delete")}
                  </button>
                  <button
                    type="button"
                    className="btn btn-light"
                    onClick={() => setConfirmDelete(false)}
                  >
                    {t("common.cancel")}
                  </button>
                </div>
              </form>
            )}
          </Card>
        </>
      )}
    </>
  );
}
