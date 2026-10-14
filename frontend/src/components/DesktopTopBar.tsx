"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Camera, ChevronDown, Search } from "lucide-react";
import { navGroups } from "@/data/dashboard";
import { useI18n } from "@/i18n";
import { useApp } from "./AppState";
import Avatar from "./Avatar";
import LanguageSelect from "./LanguageSelect";
export default function DesktopTopBar() {
  const { t } = useI18n(),
    { data } = useApp(),
    path = usePathname(),
    router = useRouter();
  const current = navGroups
    .flatMap((g) => g.items)
    .find(
      (i) =>
        i.href === path || (i.href !== "/" && path.startsWith(i.href + "/")),
    );
  return (
    <header className="d-none d-lg-flex sticky-top align-items-center justify-content-between gap-3 bg-white border-bottom px-4 py-3 tw:z-[1010]">
      <div>
        <h1 className="h4 fw-bold mb-0">{t(current?.key ?? "nav.home")}</h1>
        <p className="text-body-secondary small mb-0">{t("home.principle")}</p>
      </div>
      <form
        role="search"
        className="flex-grow-1 tw:max-w-md"
        onSubmit={(e) => {
          e.preventDefault();
          const q = String(new FormData(e.currentTarget).get("q") ?? "");
          router.push(`/search?q=${encodeURIComponent(q)}`);
        }}
      >
        <div className="input-group">
          <span className="input-group-text bg-body-tertiary border-end-0">
            <Search size={18} aria-hidden />
          </span>
          <input
            name="q"
            type="search"
            className="form-control bg-body-tertiary border-start-0 shadow-none"
            placeholder={t("search.title")}
            aria-label={t("search.placeholder")}
          />
        </div>
      </form>
      <div className="d-flex align-items-center gap-2">
        <LanguageSelect compact />
        <Link
          href="/profile"
          className="btn btn-light border d-flex align-items-center gap-2 rounded-pill ps-1 pe-3 py-1 account-chip"
        >
          <span className="account-name fw-semibold small">
            <bdi>{data?.learner.display_name ?? t("home.defaultLearner")}</bdi>
          </span>
          <span className="profile-avatar-wrap">
            <Avatar src={null} size={38} tone="onLight" />
            <span className="profile-avatar-hint" aria-hidden="true">
              <Camera size={11} strokeWidth={2.4} />
            </span>
          </span>
          <ChevronDown className="account-chevron" size={16} aria-hidden />
        </Link>
      </div>
    </header>
  );
}
