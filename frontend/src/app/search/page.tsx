import { SearchScreen } from "@/components/screens/UtilityScreens";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  return <SearchScreen initialQuery={(await searchParams).q ?? ""} />;
}
