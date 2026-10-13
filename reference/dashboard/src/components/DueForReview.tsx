import { dueReviews } from "@/data/dashboard";

/**
 * Titles that have come back for spaced review (1, 3, 7, 14 and 30 day ladder).
 * Mobile: icon, title and source, three rows (mirrors the reference list).
 * Desktop: adds the interval badge and a fourth row.
 */
export default function DueForReview() {
  return (
    <section id="review" aria-labelledby="review-title" className="tw:mt-7 tw:lg:mt-6">
      <div className="d-flex align-items-center justify-content-between mb-3 px-1">
        <h2 id="review-title" className="h5 fw-bold mb-0">
          Due for Review
        </h2>
        <a href="#review" className="fw-semibold text-decoration-none small">
          View All
        </a>
      </div>

      <div className="card border-0 shadow-sm rounded-4 overflow-hidden">
        <ul className="list-unstyled m-0">
          {dueReviews.map(({ title, source, interval, icon: Icon, color, ink, tint }, i) => (
            <li key={title} className={`event-row${i === 3 ? " d-none d-lg-block" : ""}`}>
              <a
                href="#review"
                className="d-flex align-items-center gap-3 px-3 py-3 text-reset text-decoration-none tw:hover:bg-surface"
              >
                <span
                  className="tw:grid tw:size-11 tw:shrink-0 tw:place-items-center tw:rounded-xl"
                  style={{ backgroundColor: tint, color }}
                >
                  <Icon size={22} aria-hidden="true" />
                </span>
                <span className="flex-grow-1 min-w-0">
                  <span className="d-block fw-semibold tw:text-[15px]">{title}</span>
                  <span className="d-block text-body-secondary tw:text-[13px]">{source}</span>
                </span>
                <span
                  className="badge rounded-pill d-none d-lg-inline-block fw-semibold"
                  style={{ backgroundColor: tint, color: ink }}
                >
                  {interval}
                </span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
