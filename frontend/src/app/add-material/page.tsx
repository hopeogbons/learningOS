import UploadScreen from "@/components/screens/UploadScreen";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ collection?: string }>;
}) {
  return (
    <UploadScreen initialCollection={(await searchParams).collection ?? ""} />
  );
}
