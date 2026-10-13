"use client";

import { useEffect, useId, useState } from "react";
import { Bell, LogOut, X } from "lucide-react";
import { learner, navGroups } from "@/data/dashboard";
import Avatar from "./Avatar";
import Logo from "./Logo";

/**
 * Mobile-only blue header: menu button, logo, notifications and the greeting.
 * The menu opens a Bootstrap offcanvas drawer driven by React state, so no
 * Bootstrap JavaScript bundle is needed.
 */
export default function MobileHero() {
  const [open, setOpen] = useState(false);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open]);

  return (
    <>
      <header className="hero d-lg-none">
        <div className="hero-bar">
          <button
            type="button"
            className="icon-btn"
            aria-label="Open menu"
            aria-expanded={open}
            onClick={() => setOpen(true)}
          >
            <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden="true">
              <path d="M3 6h20M3 13h20M3 20h12" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
            </svg>
          </button>
          <Logo tone="light" size={32} className="tw:justify-self-center" />
          <button type="button" className="icon-btn tw:justify-self-end" aria-label="Notifications, 2 new">
            <Bell size={26} strokeWidth={2} aria-hidden="true" />
            <span className="dot-badge dot-badge--hero" />
          </button>
        </div>

        <div className="hero-greeting">
          <Avatar src={learner.avatarSrc} size={84} tone="onDark" />
          <div>
            <p className="mb-1 tw:text-[15px] tw:text-white/90">{learner.greeting},</p>
            <h1 className="mb-1 tw:text-2xl tw:leading-tight tw:font-bold">{learner.name}</h1>
            <p className="mb-0 tw:text-[15px] tw:text-white/90">
              {learner.collections} Collections &middot; {learner.dueToday} due today
            </p>
          </div>
        </div>
      </header>

      {/* Drawer */}
      <div
        className={`offcanvas offcanvas-start${open ? " show" : ""}`}
        tabIndex={-1}
        aria-labelledby={titleId}
        aria-hidden={!open}
        inert={!open}
        style={{ width: 296 }}
      >
        <div className="offcanvas-header justify-content-between">
          <span id={titleId}>
            <Logo size={38} />
          </span>
          <button type="button" className="icon-btn icon-btn--light" aria-label="Close menu" onClick={() => setOpen(false)}>
            <X size={20} aria-hidden="true" />
          </button>
        </div>
        <div className="offcanvas-body d-flex flex-column pt-0">
          <nav aria-label="Main" className="drawer-nav">
            {navGroups.map((group, gi) => (
              <div key={group.label ?? "home"} className={gi === 0 ? "" : "mt-3"}>
                {group.label && <p className="nav-group-label">{group.label}</p>}
                <ul className="nav flex-column gap-1">
                  {group.items.map(({ label, icon: Icon, href }) => {
                    const current = href === "#home";
                    return (
                      <li className="nav-item" key={label}>
                        <a
                          className={`nav-link${current ? " active" : ""}`}
                          href={href}
                          aria-current={current ? "page" : undefined}
                          onClick={() => setOpen(false)}
                        >
                          <Icon size={20} aria-hidden="true" />
                          {label}
                        </a>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
          <button type="button" className="btn btn-outline-secondary d-flex align-items-center justify-content-center gap-2 mt-auto">
            <LogOut size={18} aria-hidden="true" /> Log out
          </button>
        </div>
      </div>
      {open && <div className="offcanvas-backdrop fade show" onClick={() => setOpen(false)} />}
    </>
  );
}
