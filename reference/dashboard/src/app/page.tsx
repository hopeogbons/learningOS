import BottomNav from "@/components/BottomNav";
import DesktopGreeting from "@/components/DesktopGreeting";
import { CalibrationCard, CollectionsPanel, RecentMaterials, StatsRow } from "@/components/DesktopPanels";
import DesktopTopBar from "@/components/DesktopTopBar";
import DueForReview from "@/components/DueForReview";
import MobileHero from "@/components/MobileHero";
import QuickActions from "@/components/QuickActions";
import Sidebar from "@/components/Sidebar";

export default function HomePage() {
  return (
    <>
      <Sidebar />
      <div className="app-main">
        <MobileHero />
        <DesktopTopBar />

        <main className="app-content">
          <DesktopGreeting />
          <QuickActions />
          <StatsRow />

          <div className="row gx-0 gx-xl-4 gy-0">
            <div className="col-12 col-xl-7">
              <DueForReview />
              <CollectionsPanel />
            </div>
            <div className="col-12 col-xl-5 d-none d-lg-block tw:mt-6">
              <CalibrationCard />
              <RecentMaterials />
            </div>
          </div>
        </main>

        <BottomNav />
      </div>
    </>
  );
}
