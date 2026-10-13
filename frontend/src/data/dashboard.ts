import {
  BookOpenCheck,
  ChartNoAxesColumn,
  CircleUserRound,
  FilePlus2,
  FolderOpen,
  House,
  ListChecks,
  Mic,
  Plug,
  Repeat,
  Lightbulb,
  GraduationCap,
  Music,
  FileText,
  Camera,
  Globe,
  CirclePlay,
  Link2,
  type LucideIcon,
} from "lucide-react";
export const product = { name: "Learning OS" };
export type NavItem = { key: string; icon: LucideIcon; href: string };
export const navGroups: { key: string | null; items: NavItem[] }[] = [
  { key: null, items: [{ key: "nav.home", icon: House, href: "/" }] },
  {
    key: "nav.learn",
    items: [
      { key: "nav.study", icon: BookOpenCheck, href: "/study" },
      { key: "nav.review", icon: Repeat, href: "/review" },
      { key: "nav.outline", icon: ListChecks, href: "/outline" },
    ],
  },
  {
    key: "nav.library",
    items: [
      { key: "nav.collections", icon: FolderOpen, href: "/collections" },
      { key: "nav.addMaterial", icon: FilePlus2, href: "/add-material" },
    ],
  },
  {
    key: "nav.insights",
    items: [
      { key: "nav.progress", icon: ChartNoAxesColumn, href: "/progress" },
    ],
  },
  {
    key: "nav.account",
    items: [
      { key: "nav.connections", icon: Plug, href: "/connections" },
      { key: "nav.profile", icon: CircleUserRound, href: "/profile" },
    ],
  },
];
export const tabItems = [
  navGroups[0].items[0],
  navGroups[2].items[0],
  navGroups[1].items[0],
  navGroups[1].items[1],
];
export const quickActions = [
  {
    key: "nav.study",
    icon: BookOpenCheck,
    color: "#2F7BEB",
    detail: "home.studyDetail",
    href: "/study",
  },
  {
    key: "nav.review",
    icon: Repeat,
    color: "#F59E0B",
    detail: "home.reviewDetail",
    href: "/review",
  },
  {
    key: "nav.addMaterial",
    icon: FilePlus2,
    color: "#22B14C",
    detail: "home.addDetail",
    href: "/add-material",
  },
  {
    key: "nav.outline",
    icon: ListChecks,
    color: "#7C5CE6",
    detail: "home.outlineDetail",
    href: "/outline",
  },
  {
    key: "nav.voice",
    icon: Mic,
    color: "#E5444F",
    detail: "home.voiceDetail",
    href: "/study?mode=voice",
  },
  {
    key: "nav.progress",
    icon: ChartNoAxesColumn,
    color: "#14B8A6",
    detail: "home.progressDetail",
    href: "/progress",
  },
];
export function collectionStyle(key?: string) {
  const styles = {
    teal: { icon: Lightbulb, color: "#0D9488", tint: "#E3F7F4" },
    blue: { icon: GraduationCap, color: "#2F7BEB", tint: "#EAF3FF" },
    purple: { icon: Music, color: "#7C5CE6", tint: "#F1ECFF" },
  };
  return styles[key as keyof typeof styles] ?? styles.blue;
}
export function materialIcon(kind?: string) {
  return (
    (
      {
        photo: Camera,
        image: Camera,
        web: Globe,
        url: Link2,
        youtube: CirclePlay,
        captions: CirclePlay,
      } as Record<string, LucideIcon>
    )[kind ?? ""] ?? FileText
  );
}
export function isCurrent(path: string, href: string) {
  return href === "/"
    ? path === "/"
    : path === href || path.startsWith(`${href}/`);
}
