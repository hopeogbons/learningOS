"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { navGroups, isCurrent } from "@/data/dashboard";
import { useI18n } from "@/i18n";
export default function Sidebar() {
  const path = usePathname(),
    { t } = useI18n();
  return (
    <aside
      className="sidebar d-none d-lg-flex flex-column"
      aria-label={t("nav.sidebar")}
    >
      <nav aria-label={t("nav.main")} className="flex-grow-1 overflow-auto">
        {navGroups.map((group, gi) => (
          <div key={group.key ?? "home"} className={gi === 0 ? "" : "mt-3"}>
            {group.key && <p className="nav-group-label">{t(group.key)}</p>}
            <ul className="nav flex-column gap-1">
              {group.items.map(({ key, icon: Icon, href }) => (
                <li className="nav-item" key={key}>
                  <Link
                    href={href}
                    className={`nav-link${isCurrent(path, href) ? " active" : ""}`}
                    aria-current={isCurrent(path, href) ? "page" : undefined}
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
        href="/logout"
        className="btn btn-link text-body-secondary text-decoration-none d-flex align-items-center gap-2 mt-3 px-3"
      >
        <LogOut size={18} aria-hidden />
        {t("common.logout")}
      </Link>
    </aside>
  );
}
