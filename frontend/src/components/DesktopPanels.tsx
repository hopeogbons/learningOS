"use client";
import Link from "next/link";
import { Cloud } from "lucide-react";
import { useI18n } from "@/i18n";
import { useApp } from "./AppState";
import { collectionStyle, materialIcon } from "@/data/dashboard";
import type { Collection, Calibration } from "@/lib/api";
import { Empty, StorageBadge } from "./Shared";
export function PanelHeader({
  id,
  title,
  action,
  href,
}: {
  id: string;
  title: string;
  action?: string;
  href?: string;
}) {
  return (
    <div className="d-flex align-items-center justify-content-between mb-3 gap-2">
      <h2 id={id} className="h6 fw-bold mb-0">
        {title}
      </h2>
      {action && href && (
        <Link href={href} className="fw-semibold text-decoration-none small">
          {action}
        </Link>
      )}
    </div>
  );
}
export function StatsRow() {
  const { t } = useI18n(),
    { data } = useApp();
  const p = data?.scope_progress;
  const stats = [
    {
      label: "home.scopeComplete",
      value: `${p?.percent ?? 0}%`,
      note: t("common.doneOf", {
        done: p?.completed_count ?? 0,
        total: p?.total_in_scope ?? 0,
      }),
      color: "#7C5CE6",
      percent: p?.percent ?? 0,
    },
    {
      label: "home.dueReview",
      value: String(data?.due_count ?? 0),
      note: t("home.today"),
      color: "#F59E0B",
    },
    {
      label: "home.weakSpots",
      value: String(p?.review_needed_count ?? 0),
      note: t("home.weakNote"),
      color: "#E5444F",
    },
    {
      label: "nav.collections",
      value: String(data?.collections_count ?? 0),
      note: t("home.driveCount", {
        count:
          data?.collections.filter((c) => c.provisioning_state === "ready")
            .length ?? 0,
      }),
      color: "#0D9488",
    },
  ];
  return (
    <section
      aria-label={t("home.summary")}
      className="d-none d-lg-block tw:mt-6"
    >
      <div className="row g-3">
        {stats.map((s) => (
          <div className="col-6 col-xxl-3" key={s.label}>
            <div className="card border-0 shadow-sm rounded-4 h-100">
              <div className="card-body p-4">
                <p className="text-body-secondary fw-medium small mb-2">
                  {t(s.label)}
                </p>
                <p className="fw-bold mb-1 tw:text-3xl tw:leading-none">
                  {s.value}
                </p>
                <p className="text-body-secondary small mb-3">{s.note}</p>
                <div className="progress tw:h-1.5" role="presentation">
                  <div
                    className="progress-bar"
                    style={{
                      width: s.percent === undefined ? "0%" : `${s.percent}%`,
                      backgroundColor: s.color,
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
export function CollectionRow({ collection: c }: { collection: Collection }) {
  const { t } = useI18n(),
    { icon: Icon, color, tint } = collectionStyle(c.color_key);
  return (
    <div className="d-flex align-items-center gap-3">
      <span
        className="tw:grid tw:size-11 tw:shrink-0 tw:place-items-center tw:rounded-xl"
        style={{ backgroundColor: tint, color }}
      >
        <Icon size={22} aria-hidden />
      </span>
      <span className="flex-grow-1 min-w-0">
        <span className="d-flex align-items-center justify-content-between gap-2">
          <Link
            href={`/collections/${c.id}/outline`}
            className="fw-semibold tw:text-[15px] text-reset text-decoration-none"
          >
            <bdi>{c.name}</bdi>
          </Link>
          <span className="text-body-secondary tw:text-xs tw:shrink-0">
            {t("common.doneOf", {
              done: c.progress?.completed_count ?? 0,
              total: c.progress?.total_in_scope ?? 0,
            })}
          </span>
        </span>
        <span className="d-block text-body-secondary mb-2 tw:text-xs">
          <bdi>{c.note}</bdi> &middot;{" "}
          {t("common.materialCount", { count: c.material_count ?? 0 })}
        </span>
        <span
          className="progress d-flex tw:h-1.5"
          role="progressbar"
          aria-label={t("home.scopeProgress")}
          aria-valuenow={c.progress?.percent ?? 0}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <span
            className="progress-bar"
            style={{
              width: `${c.progress?.percent ?? 0}%`,
              backgroundColor: color,
            }}
          />
        </span>
      </span>
      <span className="d-inline-flex align-items-center gap-1">
        <Cloud size={12} aria-hidden />
        <StorageBadge
          state={
            c.storage_mode === "drive" && c.provisioning_state === "ready"
              ? "drive_ready"
              : c.storage_mode === "drive"
                ? c.provisioning_state
                : "local"
          }
        />
      </span>
    </div>
  );
}
export function CollectionsPanel() {
  const { t } = useI18n(),
    { data } = useApp();
  return (
    <section
      aria-labelledby="collections-title"
      className="d-none d-lg-block card border-0 shadow-sm rounded-4 tw:mt-6"
    >
      <div className="card-body p-4">
        <PanelHeader
          id="collections-title"
          title={t("home.yourCollections")}
          action={t("home.manage")}
          href="/collections"
        />
        <ul className="list-unstyled m-0 d-flex flex-column gap-4">
          {data?.collections.map((c) => (
            <li key={c.id}>
              <CollectionRow collection={c} />
            </li>
          ))}
        </ul>
        {!data?.collections.length && (
          <Empty href="/collections" label={t("collection.create")}>
            {t("home.noCollections")}
          </Empty>
        )}
      </div>
    </section>
  );
}
export function CalibrationCard({
  full = false,
  calibration,
}: {
  full?: boolean;
  calibration?: Calibration;
}) {
  const { t } = useI18n(),
    { data } = useApp(),
    p = calibration ?? data?.calibration;
  return (
    <section
      aria-labelledby="progress-title"
      className={`${full ? "" : "d-none d-lg-block "}card border-0 shadow-sm rounded-4`}
    >
      <div className="card-body p-4">
        <PanelHeader
          id="progress-title"
          title={t("home.calibration")}
          action={full ? undefined : t("home.details")}
          href="/progress"
        />
        <ul className="list-unstyled m-0 d-flex flex-column gap-3">
          {[
            { key: "home.confidence", value: p?.confidence, color: "#F59E0B" },
            { key: "home.accuracy", value: p?.accuracy, color: "#173b3f" },
          ].map((row) => (
            <li key={row.key}>
              <div className="d-flex justify-content-between mb-1 tw:text-sm">
                <span className="fw-medium">{t(row.key)}</span>
                <span className="text-body-secondary">
                  {row.value === null || row.value === undefined
                    ? "—"
                    : `${Math.round(row.value)}%`}
                </span>
              </div>
              <div
                className="progress tw:h-2"
                role="progressbar"
                aria-label={t(row.key)}
                aria-valuenow={Math.round(row.value ?? 0)}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="progress-bar"
                  style={{
                    width: `${Math.round(row.value ?? 0)}%`,
                    backgroundColor: row.color,
                  }}
                />
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-3 mb-0 rounded-3 bg-body-tertiary px-3 py-2 text-body-secondary tw:text-sm">
          {(p?.sample_count ?? 0) < 5
            ? t("common.noHistory")
            : t("home.calibrationNote")}
        </p>
        <p className="small text-body-secondary mt-2 mb-0">
          {t("progress.sample", { count: p?.sample_count ?? 0 })}
        </p>
      </div>
    </section>
  );
}
export function RecentMaterials() {
  const { t } = useI18n(),
    { data } = useApp();
  return (
    <section
      aria-labelledby="materials-title"
      className="d-none d-lg-block card border-0 shadow-sm rounded-4 tw:mt-6"
    >
      <div className="card-body p-4">
        <PanelHeader
          id="materials-title"
          title={t("home.recent")}
          action={t("nav.addMaterial")}
          href="/add-material"
        />
        <ul className="list-unstyled m-0 d-flex flex-column gap-3">
          {data?.recent_materials.map((m) => {
            const Icon = materialIcon(m.source_type);
            return (
              <li key={m.id} className="d-flex align-items-center gap-3">
                <span className="tw:grid tw:size-9 tw:shrink-0 tw:place-items-center tw:rounded-lg tw:bg-brand-50 tw:text-brand-600">
                  <Icon size={18} aria-hidden />
                </span>
                <span className="flex-grow-1 min-w-0">
                  <span className="d-block fw-medium tw:text-sm">
                    <bdi>{m.title}</bdi>
                  </span>
                  <span className="d-block text-body-secondary tw:text-xs">
                    <StorageBadge state={m.storage_state ?? "local"} />{" "}
                    <StorageBadge state={m.status} />
                  </span>
                </span>
                <span className="badge text-bg-light border fw-medium">
                  <bdi>{m.source_type}</bdi>
                </span>
              </li>
            );
          })}
        </ul>
        {!data?.recent_materials.length && (
          <Empty>{t("home.noMaterials")}</Empty>
        )}
      </div>
    </section>
  );
}
