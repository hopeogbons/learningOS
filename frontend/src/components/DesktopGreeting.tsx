"use client";
import Link from "next/link";
import { ArrowRight, Bell } from "lucide-react";
import { useI18n } from "@/i18n";
import { useApp } from "./AppState";
import Avatar from "./Avatar";
import LearningPattern from "./LearningPattern";
import Logo from "./Logo";
export default function DesktopGreeting() {
  const { t } = useI18n(),
    { data } = useApp();
  const progress = data?.scope_progress;
  const resume = data?.resume;
  return (
    <header className="desktop-greeting d-none d-lg-block position-relative overflow-hidden" aria-label={t("home.welcome")}>
      <LearningPattern />
      <div className="desktop-hero-inner">
        <div className="desktop-hero-brandbar">
          <Logo size={40} />
          <Link
            href="/notifications"
            className="icon-btn icon-btn--hero"
            aria-label={t("common.notifications")}
          >
            <Bell size={22} aria-hidden />
          </Link>
        </div>
        <div className="desktop-greeting-row">
          <div className="greeting-content d-flex align-items-center gap-4 position-relative">
            <Avatar src={null} size={88} tone="onDark" />
            <div>
              <p className="greeting-eyebrow mb-1">{t("home.greeting")},</p>
              <h2 className="fw-bold mb-3 tw:text-3xl">
                <bdi>{data?.learner.display_name ?? t("home.defaultLearner")}</bdi>
              </h2>
              <div className="d-flex flex-wrap gap-2">
                {[
                  t("home.collectionCount", {
                    count: data?.collections_count ?? 0,
                  }),
                  t("home.dueCount", { count: data?.due_count ?? 0 }),
                ].map((chip) => (
                  <span key={chip} className="greeting-chip">
                    {chip}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div className="greeting-content greeting-resume">
            <p className="greeting-eyebrow text-uppercase fw-semibold mb-2">
              {t("home.continue")}
            </p>
            <p className="fw-bold mb-1 tw:text-xl">
              <bdi>{resume?.title ?? t("nav.study")}</bdi>
            </p>
            <p className="greeting-resume-note mb-3 tw:text-sm">
              {resume
                ? data?.collections.find((c) => c.id === resume.collection_id)?.name
                : t("home.pickScope")}
            </p>
            <div className="d-flex align-items-center gap-2 mb-3">
              <div
                className="greeting-progress-track progress flex-grow-1"
                role="progressbar"
                aria-label={t("home.scopeProgress")}
                aria-valuenow={progress?.percent ?? 0}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div className="progress-bar" style={{ width: `${progress?.percent ?? 0}%` }} />
              </div>
              <span className="greeting-resume-note small">
                {t("common.doneOf", {
                  done: progress?.completed_count ?? 0,
                  total: progress?.total_in_scope ?? 0,
                })}
              </span>
            </div>
            <Link
              href={resume
                ? `/study?session=${encodeURIComponent(resume.session_id ?? resume.id ?? "")}`
                : "/outline"}
              className="btn btn-light btn-sm fw-semibold d-inline-flex align-items-center gap-2 text-primary"
            >
              {t(resume ? "home.resume" : "nav.outline")}
              <ArrowRight size={16} aria-hidden />
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}
