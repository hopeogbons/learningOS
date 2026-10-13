import { LogOut } from "lucide-react";
import { navGroups } from "@/data/dashboard";
import Logo from "./Logo";

/** Desktop-only fixed navigation, grouped by what the learner is doing. */
export default function Sidebar() {
  return (
    <aside className="sidebar d-none d-lg-flex flex-column" aria-label="Sidebar">
      <a href="#home" className="d-inline-flex text-decoration-none px-2 mb-4" aria-label="Learning OS home">
        <Logo size={44} />
      </a>

      <nav aria-label="Main" className="flex-grow-1 overflow-auto">
        {navGroups.map((group, gi) => (
          <div key={group.label ?? "home"} className={gi === 0 ? "" : "mt-3"}>
            {group.label && <p className="nav-group-label">{group.label}</p>}
            <ul className="nav flex-column gap-1">
              {group.items.map(({ label, icon: Icon, href }) => {
                const current = href === "#home";
                return (
                  <li className="nav-item" key={label}>
                    <a className={`nav-link${current ? " active" : ""}`} href={href} aria-current={current ? "page" : undefined}>
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

      <button type="button" className="btn btn-link text-body-secondary text-decoration-none d-flex align-items-center gap-2 mt-3 px-3">
        <LogOut size={18} aria-hidden="true" /> Log out
      </button>
    </aside>
  );
}
