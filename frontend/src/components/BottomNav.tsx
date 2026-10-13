"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { tabItems, isCurrent } from "@/data/dashboard";
import { useI18n } from "@/i18n";
export default function BottomNav() {
  const path = usePathname(),
    { t } = useI18n();
  return (
    <nav className="bottom-nav d-lg-none" aria-label={t("nav.primary")}>
      <ul className="list-unstyled d-grid m-0 mx-auto tw:max-w-xl tw:grid-cols-4">
        {tabItems.map(({ key, icon: Icon, href }) => (
          <li key={key}>
            <Link
              href={href}
              aria-current={isCurrent(path, href) ? "page" : undefined}
            >
              <Icon
                size={24}
                strokeWidth={isCurrent(path, href) ? 2.4 : 2}
                fill={isCurrent(path, href) ? "currentColor" : "none"}
                aria-hidden
              />
              {t(key)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
