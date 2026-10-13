import { ArrowRight } from "lucide-react";
import { learner, resume } from "@/data/dashboard";
import Avatar from "./Avatar";

/** Desktop-only welcome banner with a single "pick up where you left off" card. */
export default function DesktopGreeting() {
  return (
    <section
      id="home"
      className="d-none d-lg-flex align-items-center justify-content-between gap-4 position-relative overflow-hidden text-white mb-4 tw:mt-6 tw:rounded-3xl tw:bg-linear-to-br tw:from-brand-700 tw:via-brand-600 tw:to-brand-500 tw:p-7 tw:shadow-xl tw:shadow-brand-900/20"
      aria-label="Welcome"
    >
      <span aria-hidden="true" className="position-absolute tw:-top-16 tw:right-40 tw:size-56 tw:rounded-full tw:bg-white/10" />
      <span aria-hidden="true" className="position-absolute tw:-bottom-24 tw:right-4 tw:size-64 tw:rounded-full tw:bg-white/10" />

      <div className="d-flex align-items-center gap-4 position-relative">
        <Avatar src={learner.avatarSrc} size={88} tone="onDark" />
        <div>
          <p className="mb-1 tw:text-white/85">{learner.greeting},</p>
          <h2 className="fw-bold mb-3 tw:text-3xl">{learner.name}</h2>
          <div className="d-flex flex-wrap gap-2">
            {[`${learner.collections} Collections`, `${learner.dueToday} titles due today`].map((chip) => (
              <span key={chip} className="tw:rounded-full tw:bg-white/15 tw:px-3 tw:py-1 tw:text-xs tw:font-medium">
                {chip}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="position-relative tw:w-80 tw:shrink-0 tw:rounded-2xl tw:bg-white/15 tw:p-4 tw:backdrop-blur">
        <p className="text-uppercase fw-semibold mb-2 tw:text-[11px] tw:tracking-widest tw:text-white/85">Continue studying</p>
        <p className="fw-bold mb-1 tw:text-xl">{resume.title}</p>
        <p className="mb-3 tw:text-sm tw:text-white/90">{resume.where}</p>
        <div className="d-flex align-items-center gap-2 mb-3">
          <div
            className="progress flex-grow-1 tw:h-1.5 tw:bg-white/25"
            role="progressbar"
            aria-label="Scope progress"
            aria-valuenow={resume.percent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div className="progress-bar" style={{ width: `${resume.percent}%`, backgroundColor: "#FBB040" }} />
          </div>
          <span className="tw:text-xs tw:font-medium">
            {resume.done} of {resume.total}
          </span>
        </div>
        <a href="#study" className="btn btn-light btn-sm fw-semibold d-inline-flex align-items-center gap-2 text-primary">
          Resume <ArrowRight size={16} aria-hidden="true" />
        </a>
      </div>
    </section>
  );
}
