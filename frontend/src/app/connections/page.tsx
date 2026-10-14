import ConnectionsScreen from "@/components/screens/ConnectionsScreen";
import { Suspense } from "react";
import { Status } from "@/components/Shared";
export default function Page() {
  return <Suspense fallback={<Status loading />}><ConnectionsScreen /></Suspense>;
}
