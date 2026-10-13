import { Cloud } from "lucide-react";
import { collections, materials, progress } from "@/data/dashboard";

/* Desktop-only detail cards. Each one is hidden below the lg breakpoint so the
   mobile screen stays focused on the shortcuts and the review list. */

function PanelHeader({ id, title, action }: { id: string; title: string; action?: string }) {
  return (
    <div className="d-flex align-items-center justify-content-between mb-3">
      <h2 id={id} className="h6 fw-bold mb-0">
        {title}
      </h2>
      {action && (
        <a href={`#${id.replace("-title", "")}`} className="fw-semibold text-decoration-none small">
          {action}
        </a>
      )}
    </div>
  );
}

/** Four summary numbers, one line each. */
export function StatsRow() {
  const stats = [
    { label: "Scope complete", value: `${progress.percent}%`, note: `${progress.done} of ${progress.total} titles`, color: "#7C5CE6", percent: progress.percent },
    { label: "Due for review", value: "5", note: "Titles due today", color: "#F59E0B", percent: 62 },
    { label: "Weak spots", value: String(progress.weakSpots), note: "Will come back sooner", color: "#E5444F", percent: 30 },
    { label: "Collections", value: "3", note: "2 synced with Drive", color: "#0D9488", percent: 66 },
  ];
  return (
    <section aria-label="Summary" className="d-none d-lg-block tw:mt-6">
      <div className="row g-3">
        {stats.map(({ label, value, note, color, percent }) => (
          <div className="col-6 col-xxl-3" key={label}>
            <div className="card border-0 shadow-sm rounded-4 h-100">
              <div className="card-body p-4">
                <p className="text-body-secondary fw-medium small mb-2">{label}</p>
                <p className="fw-bold mb-1 tw:text-3xl tw:leading-none">{value}</p>
                <p className="text-body-secondary small mb-3">{note}</p>
                <div className="progress tw:h-1.5" role="presentation">
                  <div className="progress-bar" style={{ width: `${percent}%`, backgroundColor: color }} />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/** Collections: folder-like groupings, each optionally tied to a Google Drive folder. */
export function CollectionsPanel() {
  return (
    <section id="collections" aria-labelledby="collections-title" className="d-none d-lg-block card border-0 shadow-sm rounded-4 tw:mt-6">
      <div className="card-body p-4">
        <PanelHeader id="collections-title" title="Your Collections" action="Manage" />
        <ul className="list-unstyled m-0 d-flex flex-column gap-4">
          {collections.map(({ name, note, done, total, percent, materials: count, drive, icon: Icon, color, tint }) => (
            <li key={name} className="d-flex align-items-center gap-3">
              <span className="tw:grid tw:size-11 tw:shrink-0 tw:place-items-center tw:rounded-xl" style={{ backgroundColor: tint, color }}>
                <Icon size={22} aria-hidden="true" />
              </span>
              <span className="flex-grow-1 min-w-0">
                <span className="d-flex align-items-center justify-content-between gap-2">
                  <span className="fw-semibold tw:text-[15px]">{name}</span>
                  <span className="text-body-secondary tw:text-xs tw:shrink-0">
                    {done} of {total} titles
                  </span>
                </span>
                <span className="d-block text-body-secondary mb-2 tw:text-xs">
                  {note} &middot; {count} materials
                </span>
                <span
                  className="progress d-flex tw:h-1.5"
                  role="progressbar"
                  aria-label={`${name} progress`}
                  aria-valuenow={percent}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <span className="progress-bar" style={{ width: `${percent}%`, backgroundColor: color }} />
                </span>
              </span>
              <span
                className={`badge rounded-pill fw-medium d-inline-flex align-items-center gap-1 ${drive ? "text-bg-light border" : "text-bg-light border text-body-secondary"}`}
                title={drive ? "Synced with a Google Drive folder" : "Not linked to Drive"}
              >
                <Cloud size={12} aria-hidden="true" />
                {drive ? "Drive" : "Local"}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/** Confidence versus accuracy: the gap the Reviewer watches. */
export function CalibrationCard() {
  const rows = [
    { label: "Confidence", value: progress.confidence, color: "#F59E0B" },
    { label: "Accuracy", value: progress.accuracy, color: "#2149E0" },
  ];
  return (
    <section id="progress" aria-labelledby="progress-title" className="d-none d-lg-block card border-0 shadow-sm rounded-4">
      <div className="card-body p-4">
        <PanelHeader id="progress-title" title="Confidence vs Accuracy" action="Details" />
        <ul className="list-unstyled m-0 d-flex flex-column gap-3">
          {rows.map(({ label, value, color }) => (
            <li key={label}>
              <div className="d-flex justify-content-between mb-1 tw:text-sm">
                <span className="fw-medium">{label}</span>
                <span className="text-body-secondary">{value}%</span>
              </div>
              <div className="progress tw:h-2" role="progressbar" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
                <div className="progress-bar" style={{ width: `${value}%`, backgroundColor: color }} />
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-3 mb-0 rounded-3 bg-body-tertiary px-3 py-2 text-body-secondary tw:text-sm">{progress.note}</p>
      </div>
    </section>
  );
}

/** Recently added material, with the citation style each source type uses. */
export function RecentMaterials() {
  return (
    <section id="add-material" aria-labelledby="materials-title" className="d-none d-lg-block card border-0 shadow-sm rounded-4 tw:mt-6">
      <div className="card-body p-4">
        <PanelHeader id="materials-title" title="Recent Material" action="Add Material" />
        <ul className="list-unstyled m-0 d-flex flex-column gap-3">
          {materials.map(({ name, kind, detail, icon: Icon }) => (
            <li key={name} className="d-flex align-items-center gap-3">
              <span className="tw:grid tw:size-9 tw:shrink-0 tw:place-items-center tw:rounded-lg tw:bg-brand-50 tw:text-brand-600">
                <Icon size={18} aria-hidden="true" />
              </span>
              <span className="flex-grow-1 min-w-0">
                <span className="d-block fw-medium tw:text-sm">{name}</span>
                <span className="d-block text-body-secondary tw:text-xs">{detail}</span>
              </span>
              <span className="badge text-bg-light border fw-medium">{kind}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
