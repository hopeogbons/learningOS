"use client";
import { useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { useI18n } from "@/i18n";
import { api, list, useApi } from "@/lib/api";
import { useApp } from "../AppState";
import { Card, PageTitle, Status, Empty } from "../Shared";
export function SearchScreen({ initialQuery = "" }: { initialQuery?: string }) {
  const { t } = useI18n(),
    [q, setQ] = useState(initialQuery),
    query = useApi<{
      items: {
        id: string;
        title: string;
        collection_id: string;
        type: string;
      }[];
    }>(q ? `/search?q=${encodeURIComponent(q)}` : null);
  return (
    <>
      <PageTitle title={t("search.title")} description={t("search.hint")} />
      <Card>
        <form
          className="d-flex gap-2 mb-3"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(String(new FormData(e.currentTarget).get("q") ?? ""));
          }}
        >
          <input
            className="form-control"
            name="q"
            type="search"
            aria-label={t("search.placeholder")}
            placeholder={t("search.placeholder")}
            defaultValue={initialQuery}
            maxLength={200}
            required
            dir="auto"
          />
          <button className="btn btn-primary" aria-label={t("common.search")}>
            <Search size={20} />
          </button>
        </form>
        <Status
          loading={Boolean(q) && query.loading}
          error={query.error}
          retry={query.reload}
        />
        {list(query.data).map((i) => (
          <div className="event-row py-3" key={`${i.type}-${i.id}`}>
            <Link
              href={`/collections/${i.collection_id}/outline`}
              className="fw-medium text-decoration-none"
            >
              <bdi>{i.title}</bdi>
            </Link>
          </div>
        ))}
        {q && !query.loading && !list(query.data).length && (
          <Empty>{t("search.noResults")}</Empty>
        )}
      </Card>
    </>
  );
}
export function NotificationsScreen() {
  const { t, locale } = useI18n(),
    query = useApi<{
      items: {
        id: string;
        title: string;
        body: string;
        kind: string;
        read_at: string | null;
        created_at: string;
      }[];
    }>("/notifications"),
    [error, setError] = useState<string | null>(null);
  return (
    <>
      <PageTitle
        title={t("notices.title")}
        description={t("notices.description")}
      />
      <Status
        error={error ?? query.error}
        loading={query.loading}
        retry={query.reload}
      />
      <Card>
        {list(query.data).map((n) => (
          <div className="event-row py-3" key={n.id}>
            <div className="d-flex gap-2 align-items-start">
              <div className="flex-grow-1">
                <h2 className="h6 fw-semibold">
                  <bdi>{n.title}</bdi>
                </h2>
                <p className="small text-body-secondary mb-1" dir="auto">
                  {n.body}
                </p>
                <small className="text-body-secondary">
                  {new Date(n.created_at).toLocaleString(locale)}
                </small>
              </div>
              {!n.read_at && (
                <button
                  className="btn btn-light border btn-sm"
                  onClick={async () => {
                    try {
                      await api(`/notifications/${n.id}/read`, {
                        method: "POST",
                      });
                      query.reload();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  {t("notices.read")}
                </button>
              )}
            </div>
          </div>
        ))}
        {!query.loading && !list(query.data).length && (
          <Empty>{t("notices.empty")}</Empty>
        )}
      </Card>
    </>
  );
}
export function LogoutScreen() {
  const { t } = useI18n(),
    { data, signedOut, setSignedOut } = useApp(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null);
  return (
    <>
      <PageTitle title={t("common.logout")} />
      <Card>
        {data?.mode === "demo" ? (
          <p>{t("profile.demoLogout")}</p>
        ) : signedOut ? (
          <p role="status">{t("profile.signedOut")}</p>
        ) : (
          <button
            className="btn btn-outline-primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api("/auth/logout", { method: "POST" });
                setSignedOut(true);
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {t(busy ? "common.working" : "common.logout")}
          </button>
        )}
        <Status error={error} />
        <Link href="/" className="btn btn-light mt-3">
          {t("nav.home")}
        </Link>
      </Card>
    </>
  );
}
