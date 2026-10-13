import OutlineScreen from "@/components/screens/OutlineScreen";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <OutlineScreen initialCollection={id} />;
}
