"use client";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useI18n } from "@/i18n";
import { useApp } from "./AppState";
import Avatar from "./Avatar";
export default function DesktopGreeting() {
  const { t } = useI18n(),
    { data } = useApp();
  const progress = data?.scope_progress;
  const resume = data?.resume;
  return (
    <section
      id="home"
      className="d-none d-lg-flex align-items-center justify-content-between gap-4 position-relative overflow-hidden text-white mb-4 tw:mt-6 tw:rounded-3xl tw:bg-linear-to-br tw:from-brand-700 tw:via-brand-600 tw:to-brand-500 tw:p-7 tw:shadow-xl tw:shadow-brand-900/20"
      aria-label={t("home.welcome")}
    >
      <span
        aria-hidden
        className="position-absolute tw:-top-16 tw:right-40 tw:size-56 tw:rounded-full tw:bg-white/10"
      />
      <span
        aria-hidden
        className="position-absolute tw:-bottom-24 tw:right-4 tw:size-64 tw:rounded-full tw:bg-white/10"
      />
      <div className="d-flex align-items-center gap-4 position-relative">
        <Avatar src={null} size={88} tone="onDark" />
        <div>
          <p className="mb-1 tw:text-white/85">{t("home.greeting")},</p>
          <h2 className="fw-bold mb-3 tw:text-3xl">
            <bdi>{data?.learner.display_name ?? "Learning OS"}</bdi>
          </h2>
          <div className="d-flex flex-wrap gap-2">
            {[
              t("home.collectionCount", {
                count: data?.collections_count ?? 0,
              }),
              t("home.dueCount", { count: data?.due_count ?? 0 }),
            ].map((chip) => (
              <span
                key={chip}
                className="tw:rounded-full tw:bg-white/15 tw:px-3 tw:py-1 tw:text-xs tw:font-medium"
              >
                {chip}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="position-relative tw:w-80 tw:shrink-0 tw:rounded-2xl tw:bg-white/15 tw:p-4 tw:backdrop-blur">
        <p className="text-uppercase fw-semibold mb-2 tw:text-[11px] tw:tracking-widest tw:text-white/85">
          {t("home.continue")}
        </p>
        <p className="fw-bold mb-1 tw:text-xl">
          <bdi>{resume?.title ?? t("nav.study")}</bdi>
        </p>
        <p className="mb-3 tw:text-sm tw:text-white/90">
          {resume
            ? data?.collections.find((c) => c.id === resume.collection_id)?.name
            : t("home.pickScope")}
        </p>
        <div className="d-flex align-items-center gap-2 mb-3">
          <div
            className="progress flex-grow-1 tw:h-1.5 tw:bg-white/25"
            role="progressbar"
            aria-label={t("home.scopeProgress")}
            aria-valuenow={progress?.percent ?? 0}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="progress-bar"
              style={{
                width: `${progress?.percent ?? 0}%`,
                backgroundColor: "#FBB040",
              }}
            />
          </div>
          <span className="tw:text-xs tw:font-medium">
            {t("common.doneOf", {
              done: progress?.completed_count ?? 0,
              total: progress?.total_in_scope ?? 0,
            })}
          </span>
        </div>
        <Link
          href={
            resume
              ? `/study?session=${encodeURIComponent(resume.session_id ?? resume.id ?? "")}`
              : "/outline"
          }
          className="btn btn-light btn-sm fw-semibold d-inline-flex align-items-center gap-2 text-primary"
        >
          {t(resume ? "home.resume" : "nav.outline")}
          <ArrowRight size={16} aria-hidden />
        </Link>
      </div>
    </section>
  );
}
