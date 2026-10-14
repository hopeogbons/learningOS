"use client";
import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, LogOut, X, Search } from "lucide-react";
import { navGroups, isCurrent } from "@/data/dashboard";
import { useI18n } from "@/i18n";
import { useApp } from "./AppState";
import LanguageSelect from "./LanguageSelect";
import Avatar from "./Avatar";
import Logo from "./Logo";
import LearningPattern from "./LearningPattern";
export default function MobileHero() {
  const [open, setOpen] = useState(false),
    titleId = useId(),
    dialog = useRef<HTMLDivElement>(null),
    trigger = useRef<HTMLButtonElement>(null),
    path = usePathname(),
    { t } = useI18n(),
    { data } = useApp();
  useEffect(() => {
    if (!open) return;
    const button = trigger.current;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const el = dialog.current;
    const controls = () =>
      Array.from(
        el?.querySelectorAll<HTMLElement>(
          'a[href],button,select,input,[tabindex="0"]',
        ) ?? [],
      );
    controls()[0]?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
      if (e.key === "Tab") {
        const items = controls(),
          first = items[0],
          last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", key);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", key);
      button?.focus();
    };
  }, [open]);
  return (
    <>
      <header className="hero d-lg-none">
        <LearningPattern />
        <div className="hero-bar">
          <button
            ref={trigger}
            type="button"
            className="icon-btn"
            aria-label={t("common.openMenu")}
            aria-expanded={open}
            onClick={() => setOpen(true)}
          >
            <svg
              width="26"
              height="26"
              viewBox="0 0 26 26"
              fill="none"
              aria-hidden
            >
              <path
                d="M3 6h20M3 13h20M3 20h12"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinecap="round"
              />
            </svg>
          </button>
          <Logo size={32} className="tw:justify-self-center" />
          <Link
            href="/notifications"
            className="icon-btn tw:justify-self-end"
            aria-label={t("common.notifications")}
          >
            <Bell size={26} strokeWidth={2} aria-hidden />
          </Link>
        </div>
        <div className="hero-greeting">
          <Avatar src={null} size={84} tone="onDark" />
          <div>
            <p className="hero-greeting-label mb-1 tw:text-[15px] tw:text-white/85">
              {t("home.greeting")},
            </p>
            <h1 className="mb-1 tw:text-2xl tw:leading-tight tw:font-bold">
              <bdi>{data?.learner.display_name ?? t("home.defaultLearner")}</bdi>
            </h1>
            <p className="hero-greeting-meta mb-0 tw:text-[15px] tw:text-white/85">
              {t("home.collectionCount", {
                count: data?.collections_count ?? 0,
              })}{" "}
              &middot; {t("home.dueCount", { count: data?.due_count ?? 0 })}
            </p>
          </div>
        </div>
      </header>
      <div
        ref={dialog}
        role="dialog"
        aria-modal={open || undefined}
        className={`offcanvas offcanvas-start mobile-navigation-drawer${open ? " show" : ""}`}
        tabIndex={-1}
        aria-labelledby={titleId}
        aria-hidden={!open}
        inert={!open}
      >
        <div className="offcanvas-header justify-content-between">
          <span id={titleId}>
            <Logo size={38} />
          </span>
          <button
            type="button"
            className="icon-btn icon-btn--light"
            aria-label={t("common.closeMenu")}
            onClick={() => setOpen(false)}
          >
            <X size={20} aria-hidden />
          </button>
        </div>
        <div className="offcanvas-body d-flex flex-column pt-0">
          <nav aria-label={t("nav.main")} className="drawer-nav">
            {navGroups.map((group, gi) => (
              <div key={group.key ?? "home"} className={gi === 0 ? "" : "mt-3"}>
                {group.key && <p className="nav-group-label">{t(group.key)}</p>}
                <ul className="nav flex-column gap-1">
                  {group.items.map(({ key, icon: Icon, href }) => (
                    <li className="nav-item" key={key}>
                      <Link
                        className={`nav-link${isCurrent(path, href) ? " active" : ""}`}
                        href={href}
                        aria-current={
                          isCurrent(path, href) ? "page" : undefined
                        }
                        onClick={() => setOpen(false)}
                      >
                        <Icon size={20} aria-hidden />
                        {t(key)}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
          <Link
            href="/search"
            className="btn btn-light d-flex gap-2 my-3"
            onClick={() => setOpen(false)}
          >
            <Search size={18} />
            {t("common.search")}
          </Link>
          <LanguageSelect />
          <Link
            href="/logout"
            className="btn btn-outline-secondary d-flex align-items-center justify-content-center gap-2 mt-3"
            onClick={() => setOpen(false)}
          >
            <LogOut size={18} aria-hidden />
            {t("common.logout")}
          </Link>
        </div>
      </div>
      {open && (
        <div
          className="offcanvas-backdrop fade show"
          onClick={() => setOpen(false)}
        />
      )}
    </>
  );
}
