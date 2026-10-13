import OutlineScreen from "@/components/screens/OutlineScreen";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ collection?: string }>;
}) {
  return (
    <OutlineScreen initialCollection={(await searchParams).collection ?? ""} />
  );
}
