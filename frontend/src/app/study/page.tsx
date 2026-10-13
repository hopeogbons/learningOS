import StudyScreen from "@/components/screens/StudyScreen";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{
    collection?: string;
    scope?: string;
    session?: string;
    review?: string;
    mode?: string;
  }>;
}) {
  const q = await searchParams;
  return (
    <StudyScreen
      initialCollection={q.collection}
      initialScope={q.scope}
      initialSession={q.session}
      review={q.review}
      voice={q.mode === "voice"}
    />
  );
}
