"use client";
import { useState } from "react";
import Link from "next/link";
import { useI18n } from "@/i18n";
import {
  useApi,
  usePagedApi,
  list,
  type Collection,
  type ScopeProgress,
  type Calibration,
} from "@/lib/api";
import { Card, PageTitle, Status, Empty, CollectionPicker } from "../Shared";
import { CalibrationCard } from "../DesktopPanels";
type History = {
  id: string;
  chunk_id: string;
  confidence: number;
  correct: boolean | null;
  timestamp: string;
  correctness: string;
  reviewer?: { feedback?: string };
};
export default function ProgressScreen() {
  const { t } = useI18n(),
    [collection, setCollection] = useState(""),
    collections = usePagedApi<Collection>("/collections");
  return (
    <>
      <PageTitle
        title={t("progress.title")}
        description={t("progress.description")}
      />
      <Card className="mb-3">
        <CollectionPicker
          hasMore={collections.hasMore}
          onLoadMore={collections.loadMore}
          moreLoading={collections.moreLoading}
          items={list(collections.data)}
          value={collection}
          onChange={setCollection}
        />
      </Card>
      <ProgressDetail key={collection} collection={collection} />
    </>
  );
}
function ProgressDetail({ collection }: { collection: string }) {
  const { t, locale } = useI18n(),
    progress = useApi<ScopeProgress>(
      collection ? `/collections/${collection}/progress` : null,
    ),
    history = useApi<{ items: History[]; calibration: Calibration }>(
      collection ? `/collections/${collection}/history` : null,
    ),
    weak = useApi<{
      items: {
        concept_id: string;
        title: string;
        concept: string;
        chunk_id: string;
        next_review_at: string | null;
      }[];
    }>(collection ? `/collections/${collection}/weak-spots` : null);
  return (
    <>
      <CalibrationCard full calibration={history.data?.calibration} />
      {!collection && <Empty>{t("outline.chooseFirst")}</Empty>}
      {collection && (
        <>
          <Status
            loading={progress.loading}
            error={progress.error}
            retry={progress.reload}
          />
          <div className="row g-3 mt-1">
            <div className="col-12 col-xl-6">
              <Card>
                <h2 className="h5 fw-bold">{t("progress.scope")}</h2>
                <p className="display-6 fw-bold">
                  {progress.data?.percent ?? 0}%
                </p>
                <p className="text-body-secondary small">
                  {t("common.doneOf", {
                    done: progress.data?.completed_count ?? 0,
                    total: progress.data?.total_in_scope ?? 0,
                  })}
                </p>
                <div
                  className="progress"
                  role="progressbar"
                  aria-label={t("home.scopeProgress")}
                  aria-valuenow={progress.data?.percent ?? 0}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className="progress-bar"
                    style={{ width: `${progress.data?.percent ?? 0}%` }}
                  />
                </div>
                <p className="small text-body-secondary mt-3 mb-0">
                  {t("progress.reviewNeeded")}:{" "}
                  {progress.data?.review_needed_count ?? 0}
                </p>
              </Card>
            </div>
            <div className="col-12 col-xl-6">
              <Card>
                <h2 className="h5 fw-bold">{t("progress.window")}</h2>
                <p className="small text-body-secondary">
                  {t("progress.sample", {
                    count: history.data?.calibration.sample_count ?? 0,
                  })}
                </p>
                <dl className="mb-0">
                  <dt className="small">{t("progress.gap")}</dt>
                  <dd>{history.data?.calibration.gap ?? "—"}%</dd>
                  <dt className="small">{t("progress.brier")}</dt>
                  <dd>{history.data?.calibration.brier_score ?? "—"}</dd>
                </dl>
              </Card>
            </div>
          </div>
          <Card className="mt-4">
            <h2 className="h5 fw-bold">{t("progress.weak")}</h2>
            <Status
              error={weak.error}
              loading={weak.loading}
              retry={weak.reload}
            />
            {list(weak.data).map((w) => (
              <div className="event-row py-3" key={w.concept_id}>
                <Link
                  className="fw-semibold text-decoration-none"
                  href={`/study?review=${w.chunk_id}&collection=${collection}`}
                >
                  <bdi>{w.title}</bdi>
                </Link>
                <p className="small text-body-secondary mb-0" dir="auto">
                  {w.concept}
                </p>
              </div>
            ))}
            {!weak.loading && !list(weak.data).length && (
              <Empty>{t("progress.noWeak")}</Empty>
            )}
          </Card>
          <Card className="mt-4">
            <h2 className="h5 fw-bold">{t("progress.history")}</h2>
            <Status
              error={history.error}
              loading={history.loading}
              retry={history.reload}
            />
            {list(history.data).map((h) => (
              <div className="event-row py-3 d-flex gap-3" key={h.id}>
                <span className="flex-grow-1">
                  <bdi>{h.reviewer?.feedback ?? h.correctness}</bdi>
                  <small className="d-block text-body-secondary">
                    {new Date(h.timestamp).toLocaleString(locale)}
                  </small>
                </span>
                <span className="badge text-bg-light border align-self-start">
                  {t("home.confidence")}: {h.confidence}/5
                </span>
              </div>
            ))}
            {!history.loading && !list(history.data).length && (
              <Empty>{t("progress.noHistory")}</Empty>
            )}
          </Card>
        </>
      )}
    </>
  );
}
