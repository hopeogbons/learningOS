import {
  BookOpenCheck,
  Camera,
  ChartNoAxesColumn,
  CircleUserRound,
  CirclePlay,
  FilePlus2,
  FileText,
  FlaskConical,
  FolderOpen,
  GraduationCap,
  Globe,
  House,
  Lightbulb,
  Link2,
  ListChecks,
  Mic,
  Music,
  Plug,
  Repeat,
  type LucideIcon,
} from "lucide-react";

/* ------------------------------------------------------------------ *
 * Sample content for the Learning OS home screen.
 * Wording and structure come from the Learning OS design document and
 * build playbook. Replace these exports with real data when the API exists.
 * ------------------------------------------------------------------ */

export const product = {
  name: "Learning OS",
  tagline: "A study partner that makes you learn, not just collect answers.",
  principle: "Teach, then check, in small loops.",
  tone: "It notices what is shaky and casually resurfaces it. It is not an exam.",
};

export const learner = {
  name: "John Doe",
  greeting: "Good Morning",
  /** Set to an image URL to replace the grid placeholder avatar. */
  avatarSrc: null as string | null,
  collections: 3,
  dueToday: 5,
};

/* ----------------------------- Navigation ----------------------------- */

export type NavItem = { label: string; icon: LucideIcon; href: string };
export type NavGroup = { label: string | null; items: NavItem[] };

/**
 * One menu for the whole product. Every entry maps to a capability in the design document:
 * Study (teach and check, text or voice), Review (spaced review), Outline (scope, reorder, progress),
 * Collections (Drive-backed folders), Add material (ingestion), Progress (confidence vs accuracy),
 * Connections (Drive, Gmail, web and YouTube links).
 */
export const navGroups: NavGroup[] = [
  { label: null, items: [{ label: "Home", icon: House, href: "#home" }] },
  {
    label: "Learn",
    items: [
      { label: "Study", icon: BookOpenCheck, href: "#study" },
      { label: "Review", icon: Repeat, href: "#review" },
      { label: "Outline", icon: ListChecks, href: "#outline" },
    ],
  },
  {
    label: "Library",
    items: [
      { label: "Collections", icon: FolderOpen, href: "#collections" },
      { label: "Add Material", icon: FilePlus2, href: "#add-material" },
    ],
  },
  { label: "Insights", items: [{ label: "Progress", icon: ChartNoAxesColumn, href: "#progress" }] },
  {
    label: "Account",
    items: [
      { label: "Connections", icon: Plug, href: "#connections" },
      { label: "Profile", icon: CircleUserRound, href: "#profile" },
    ],
  },
];

/** Bottom tab bar on mobile: the four things a learner does every day. */
export const tabItems: (NavItem & { current?: boolean })[] = [
  { label: "Home", icon: House, href: "#home", current: true },
  { label: "Collections", icon: FolderOpen, href: "#collections" },
  { label: "Study", icon: BookOpenCheck, href: "#study" },
  { label: "Review", icon: Repeat, href: "#review" },
];

/* ---------------------------- Quick actions --------------------------- */

export const quickActions = [
  { label: "Study", icon: BookOpenCheck, color: "#2F7BEB", detail: "Teach and check", href: "#study" },
  { label: "Review", icon: Repeat, color: "#F59E0B", detail: "5 titles due today", href: "#review" },
  { label: "Add Material", icon: FilePlus2, color: "#22B14C", detail: "PDF, photo or link", href: "#add-material" },
  { label: "Outline", icon: ListChecks, color: "#7C5CE6", detail: "Pick your scope", href: "#outline" },
  { label: "Voice", icon: Mic, color: "#E5444F", detail: "Explain it aloud", href: "#study" },
  { label: "Progress", icon: ChartNoAxesColumn, color: "#14B8A6", detail: "2 of 5 titles done", href: "#progress" },
] as const;

/* ----------------------------- Collections ---------------------------- */

export const collections = [
  {
    name: "Personal Development",
    note: "after-school and self-training",
    done: 7,
    total: 11,
    materials: 4,
    drive: true,
    icon: Lightbulb,
    color: "#0D9488",
    tint: "#E3F7F4",
  },
  {
    name: "University Courses",
    note: "school material",
    done: 2,
    total: 5,
    materials: 3,
    drive: true,
    icon: GraduationCap,
    color: "#2F7BEB",
    tint: "#EAF3FF",
  },
  {
    name: "Musical Training",
    note: "practice and theory",
    done: 1,
    total: 6,
    materials: 2,
    drive: false,
    icon: Music,
    color: "#7C5CE6",
    tint: "#F1ECFF",
  },
].map((c) => ({ ...c, percent: Math.round((c.done / c.total) * 100) }));

/* ------------------------------ Continue ------------------------------ */

export const resume = {
  title: "Electron configuration",
  where: "University Courses · Chemistry, Chapter 3",
  done: 2,
  total: 5,
  percent: 40,
};

/* ---------------------------- Spaced review --------------------------- */

/** Review ladder from the playbook: 1, 3, 7, 14 and 30 days. A failed review drops back to 1 day. */
export const dueReviews = [
  { title: "Electron configuration", source: "chem_ch3.pdf p.4", interval: "Day 3", icon: FlaskConical, color: "#2F7BEB", ink: "#1B5CBA", tint: "#EAF3FF" },
  { title: "Ionic and covalent bonds", source: "chem_ch4.pdf p.2", interval: "Day 7", icon: FlaskConical, color: "#2F7BEB", ink: "#1B5CBA", tint: "#EAF3FF" },
  { title: "Reading a lead sheet", source: "notes_photo.jpg", interval: "Day 1", icon: Music, color: "#7C5CE6", ink: "#5A3CC2", tint: "#F1ECFF" },
  { title: "Active listening", source: "web article, para 3", interval: "Day 14", icon: Globe, color: "#0D9488", ink: "#0A6A62", tint: "#E3F7F4" },
] as const;

/* ------------------------------ Materials ----------------------------- */

export const materials = [
  { name: "chem_ch4.pdf", kind: "PDF", detail: "6 titled sections, 31 concepts", icon: FileText },
  { name: "chem_ch3.pdf", kind: "PDF", detail: "5 titled sections, 24 concepts", icon: FileText },
  { name: "notes_photo.jpg", kind: "Photo", detail: "Read from a phone photo", icon: Camera },
  { name: "Public article", kind: "Web", detail: "Cited by paragraph", icon: Link2 },
  { name: "Lecture with captions", kind: "YouTube", detail: "Cited by timestamp", icon: CirclePlay },
] as const;

/* ------------------------------ Progress ------------------------------ */

export const progress = {
  done: 2,
  total: 5,
  percent: 40,
  /** Confidence versus accuracy, both out of 100. */
  confidence: 78,
  accuracy: 70,
  note: "Slightly overconfident. Weak spots come back sooner.",
  weakSpots: 3,
};
