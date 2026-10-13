"use client";
import Link from "next/link";
import { useI18n } from "@/i18n";
import { useApi, list, type ReviewItem } from "@/lib/api";
import { collectionStyle } from "@/data/dashboard";
import { Empty, Status } from "./Shared";
export default function DueForReview({
  full = false,
  collectionId = "",
}: {
  full?: boolean;
  collectionId?: string;
}) {
  const { t } = useI18n(),
    { data, error, loading, reload } = useApi<{ items: ReviewItem[] }>(
      "/review/due",
    );
  const items = list(data).filter(
    (i) => !collectionId || i.collection_id === collectionId,
  );
  return (
    <section
      id="review"
      aria-labelledby="review-title"
      className={full ? "" : "tw:mt-7 tw:lg:mt-6"}
    >
      <div className="d-flex align-items-center justify-content-between mb-3 px-1">
        <h2 id="review-title" className="h5 fw-bold mb-0">
          {t("home.dueReview")}
        </h2>
        {!full && (
          <Link
            href="/review"
            className="fw-semibold text-decoration-none small"
          >
            {t("home.viewAll")}
          </Link>
        )}
      </div>
      <Status error={error} loading={loading} retry={reload} />
      {!loading && !error && (
        <div className="card border-0 shadow-sm rounded-4 overflow-hidden">
          <ul className="list-unstyled m-0">
            {items.slice(0, full ? undefined : 4).map((item, i) => {
              const {
                icon: Icon,
                color,
                tint,
              } = collectionStyle(
                i % 3 === 0 ? "blue" : i % 3 === 1 ? "purple" : "teal",
              );
              return (
                <li
                  key={item.chunk_id}
                  className={`event-row${!full && i === 3 ? " d-none d-lg-block" : ""}`}
                >
                  <Link
                    href={`/study?review=${encodeURIComponent(item.chunk_id)}&collection=${encodeURIComponent(item.collection_id)}`}
                    className="d-flex align-items-center gap-3 px-3 py-3 text-reset text-decoration-none tw:hover:bg-surface"
                  >
                    <span
                      className="tw:grid tw:size-11 tw:shrink-0 tw:place-items-center tw:rounded-xl"
                      style={{ backgroundColor: tint, color }}
                    >
                      <Icon size={22} aria-hidden />
                    </span>
                    <span className="flex-grow-1 min-w-0">
                      <span className="d-block fw-semibold tw:text-[15px]">
                        <bdi>{item.title}</bdi>
                      </span>
                      <span className="d-block text-body-secondary tw:text-[13px]">
                        <bdi>
                          {item.source ??
                            new Date(item.next_review_at).toLocaleDateString()}
                        </bdi>
                      </span>
                    </span>
                    <span
                      className={`badge rounded-pill fw-semibold ${full ? "" : "d-none d-lg-inline-block"}`}
                      style={{ backgroundColor: tint, color }}
                    >
                      {t("home.day", {
                        count: [1, 3, 7, 14, 30][item.stage] ?? 1,
                      })}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
          {items.length === 0 && <Empty>{t("home.noDue")}</Empty>}
        </div>
      )}
    </section>
  );
}
