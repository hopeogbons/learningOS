"use client";
import Link from "next/link";
import { quickActions } from "@/data/dashboard";
import { useI18n } from "@/i18n";
import { useApp } from "./AppState";
export default function QuickActions() {
  const { t } = useI18n(),
    { data } = useApp();
  return (
    <section
      aria-labelledby="quick-actions-title"
      className="tw:rounded-3xl tw:bg-white tw:p-5 tw:shadow-xl tw:shadow-brand-900/10 tw:lg:rounded-none tw:lg:bg-transparent tw:lg:p-0 tw:lg:shadow-none"
    >
      <h2 id="quick-actions-title" className="visually-hidden">
        {t("home.quickActions")}
      </h2>
      <ul className="quick-actions-grid list-unstyled m-0 tw:grid tw:grid-cols-3 tw:gap-x-2 tw:gap-y-5 tw:lg:grid-cols-3 tw:lg:gap-4 tw:xxl:grid-cols-6">
        {quickActions.map(({ key, icon: Icon, color, detail, href }) => (
          <li key={key}>
            <Link
              href={href}
              className="quick-tile quick-tile--stacked"
            >
              <span
                className="quick-action-icon tw:grid tw:size-16 tw:shrink-0 tw:place-items-center tw:rounded-[18px] tw:text-white tw:lg:size-14 tw:lg:rounded-2xl"
                style={{
                  backgroundColor: color,
                  boxShadow: `0 8px 16px -6px ${color}99`,
                }}
              >
                <Icon size={22} strokeWidth={1.9} aria-hidden />
              </span>
              <span className="quick-action-copy">
                <span className="quick-action-label">{t(key)}</span>
                <span className="quick-action-detail">
                  {t(detail, {
                    count: data?.due_count ?? 0,
                    done: data?.scope_progress.completed_count ?? 0,
                    total: data?.scope_progress.total_in_scope ?? 0,
                  })}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
