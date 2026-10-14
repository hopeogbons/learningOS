"use client";
import { useI18n } from "@/i18n";
import { useApp } from "./AppState";
import Sidebar from "./Sidebar";
import MobileHero from "./MobileHero";
import DesktopGreeting from "./DesktopGreeting";
import DesktopTopBar from "./DesktopTopBar";
import BottomNav from "./BottomNav";
export default function AppShell({ children }: { children: React.ReactNode }) {
  const { t } = useI18n(),
    { data } = useApp();
  return (
    <>
      <a href="#main-content" className="skip-link">
        {t("common.skip")}
      </a>
      <MobileHero />
      <DesktopGreeting />
      <div className="app-layout">
        <Sidebar />
        <div className="app-main">
          <DesktopTopBar />
          <main id="main-content" className="app-content" tabIndex={-1}>
            {data?.mode === "demo" && (
              <div role="status" className="demo-notice small">
                {t("common.demo")}
              </div>
            )}
            {children}
          </main>
          <BottomNav />
        </div>
      </div>
    </>
  );
}
