import { Bell, ChevronDown, Search } from "lucide-react";
import { learner, product } from "@/data/dashboard";
import Avatar from "./Avatar";

/** Desktop-only sticky top bar with search, notifications and the account chip. */
export default function DesktopTopBar() {
  return (
    <div className="d-none d-lg-flex sticky-top align-items-center justify-content-between gap-4 bg-white border-bottom px-4 py-3 tw:z-[1010]">
      <div>
        <h1 className="h4 fw-bold mb-0">Home</h1>
        <p className="text-body-secondary small mb-0">{product.principle}</p>
      </div>

      <form role="search" className="flex-grow-1 tw:max-w-md">
        <div className="input-group">
          <span className="input-group-text bg-body-tertiary border-end-0">
            <Search size={18} aria-hidden="true" />
          </span>
          <input
            type="search"
            className="form-control bg-body-tertiary border-start-0 shadow-none"
            placeholder="Search your material"
            aria-label="Search titles, concepts and sources"
          />
        </div>
      </form>

      <div className="d-flex align-items-center gap-2">
        <button type="button" className="icon-btn icon-btn--light" aria-label="Notifications, 2 new">
          <Bell size={20} aria-hidden="true" />
          <span className="dot-badge" />
        </button>
        <button type="button" className="btn btn-light border d-flex align-items-center gap-2 rounded-pill ps-1 pe-3 py-1 ms-2">
          <Avatar src={learner.avatarSrc} size={36} tone="onLight" />
          <span className="fw-semibold small">{learner.name}</span>
          <ChevronDown size={16} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
