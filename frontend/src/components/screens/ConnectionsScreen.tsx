"use client";
import { useState } from "react";
import { Cloud, Mail, Globe, CirclePlay, RefreshCw, Plug } from "lucide-react";
import { useI18n } from "@/i18n";
import {
  api,
  list,
  useApi,
  usePagedApi,
  type Connection,
  type Collection,
} from "@/lib/api";
import { useApp } from "../AppState";
import { Card, PageTitle, Status, StorageBadge } from "../Shared";
export default function ConnectionsScreen() {
  const { t } = useI18n(),
    { reload } = useApp(),
    query = useApi<{ items: Connection[] } | Connection[]>("/connections"),
    collections = usePagedApi<Collection>("/collections"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null),
    [notice, setNotice] = useState<string | null>(null);
  const connection = list(query.data).find((c) => c.provider === "drive");
  const connected = connection?.status === "connected";
  async function action(kind: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (kind === "connect") {
        const data = await api<{ authorization_url: string }>(
          "/connections/drive/connect",
        );
        const url = new URL(data.authorization_url);
        if (!["https:", "http:"].includes(url.protocol))
          throw new Error(t("common.error"));
        window.location.assign(url.toString());
      } else if (kind === "disconnect") {
        await api("/connections/drive/disconnect", { method: "POST" });
        query.reload();
        reload();
      } else {
        for (const c of list(collections.data).filter(
          (c) => c.storage_mode === "drive",
        ))
          await api(`/collections/${c.id}/sync`, { method: "POST" });
        setNotice(t("connections.syncQueued"));
        query.reload();
        reload();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        title={t("connections.title")}
        description={t("connections.description")}
      />
      <Status
        error={error ?? query.error}
        loading={query.loading}
        retry={query.reload}
      />
      {notice && (
        <div className="alert alert-info" role="status">
          {notice}
        </div>
      )}
      <Card className="mb-3">
        <div className="d-flex gap-3">
          <span className="source-icon">
            <Cloud size={26} />
          </span>
          <div className="flex-grow-1">
            <h2 className="h5 fw-bold">{t("connections.drive")}</h2>
            <p className="small text-body-secondary">
              {t("connections.driveHelp")}
            </p>
            <div className="d-flex align-items-center flex-wrap gap-2 mb-3">
              <StorageBadge
                state={
                  connected
                    ? "drive_ready"
                    : (connection?.status ?? "disconnected")
                }
              />
              {connection?.scopes?.map((s) => (
                <small key={s} className="text-body-secondary">
                  <bdi>{s}</bdi>
                </small>
              ))}
            </div>
            <div className="d-flex flex-wrap gap-2">
              {connected ? (
                <>
                  <button
                    className="btn btn-primary d-flex align-items-center gap-2"
                    onClick={() => action("sync")}
                    disabled={
                      busy ||
                      !list(collections.data).some(
                        (c) => c.storage_mode === "drive",
                      )
                    }
                  >
                    <RefreshCw size={16} />
                    {t("connections.sync")}
                  </button>
                  <button
                    className="btn btn-outline-secondary"
                    onClick={() => action("disconnect")}
                    disabled={busy}
                  >
                    {t("connections.disconnect")}
                  </button>
                </>
              ) : (
                <button
                  className="btn btn-primary d-flex align-items-center gap-2"
                  onClick={() => action("connect")}
                  disabled={busy}
                >
                  <Plug size={16} />
                  {t("connections.connect")}
                </button>
              )}
            </div>
          </div>
        </div>
      </Card>
      {collections.hasMore && (
        <button
          className="btn btn-light border btn-sm mb-3"
          disabled={collections.moreLoading}
          onClick={collections.loadMore}
        >
          {t(collections.moreLoading ? "common.loading" : "common.continue")}
        </button>
      )}
      {connected &&
        list(collections.data)
          .filter((c) => c.storage_mode !== "drive")
          .map((c) => (
            <Card key={c.id} className="mb-3">
              <div className="d-flex align-items-center gap-3">
                <span className="flex-grow-1 fw-semibold">
                  <bdi>{c.name}</bdi>
                </span>
                <button
                  className="btn btn-outline-primary btn-sm"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await api(`/collections/${c.id}/enable-drive`, {
                        method: "POST",
                      });
                      collections.reload();
                      reload();
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  {t("connections.connect")} {t("common.drive")}
                </button>
              </div>
            </Card>
          ))}
      {[
        {
          key: "connections.gmail",
          help: "connections.gmailHelp",
          icon: Mail,
          status: "connections.disabled",
        },
        {
          key: "connections.web",
          help: "upload.linkHelp",
          icon: Globe,
          status: "connections.available",
        },
        {
          key: "connections.captions",
          help: "upload.linkHelp",
          icon: CirclePlay,
          status: "common.attention",
        },
      ].map(({ key, help, icon: Icon, status }) => (
        <Card className="mb-3" key={key}>
          <div className="d-flex gap-3">
            <span className="source-icon">
              <Icon size={26} />
            </span>
            <div>
              <h2 className="h5 fw-bold">{t(key)}</h2>
              <p className="small text-body-secondary mb-2">{t(help)}</p>
              <span className="badge text-bg-light border">{t(status)}</span>
            </div>
          </div>
        </Card>
      ))}
    </>
  );
}
