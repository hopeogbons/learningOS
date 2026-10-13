"use client";
import DesktopGreeting from "@/components/DesktopGreeting";
import {
  CalibrationCard,
  CollectionsPanel,
  RecentMaterials,
  StatsRow,
} from "@/components/DesktopPanels";
import DueForReview from "@/components/DueForReview";
import QuickActions from "@/components/QuickActions";
import { useApp } from "@/components/AppState";
import { Status } from "@/components/Shared";
export default function HomePage() {
  const { loading, error, reload } = useApp();
  return (
    <>
      <Status error={error} loading={loading} retry={reload} />
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
    </>
  );
}
