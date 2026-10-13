import { tabItems } from "@/data/dashboard";

/** Mobile-only tab bar pinned to the bottom of the screen. */
export default function BottomNav() {
  return (
    <nav className="bottom-nav d-lg-none" aria-label="Primary">
      <ul className="list-unstyled d-grid m-0 mx-auto tw:max-w-xl tw:grid-cols-4">
        {tabItems.map(({ label, icon: Icon, href, current }) => (
          <li key={label}>
            <a href={href} aria-current={current ? "page" : undefined}>
              <Icon size={24} strokeWidth={current ? 2.4 : 2} fill={current ? "currentColor" : "none"} aria-hidden="true" />
              {label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
