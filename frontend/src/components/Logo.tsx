import { useId } from "react";

/**
 * Learning OS mark: the Bootstrap Icons "book-half" glyph (MIT licence, icons.getbootstrap.com)
 * in white on a blue tile. The path is inlined so no icon font or extra package is shipped.
 */
export function LogoMark({
  size = 40,
  className,
}: {
  size?: number;
  className?: string;
}) {
  const gid = useId();
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <defs>
        <linearGradient
          id={gid}
          x1="6"
          y1="2"
          x2="42"
          y2="46"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#3B6EF0" />
          <stop offset="1" stopColor="#1A37C9" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="14" fill={`url(#${gid})`} />
      <path
        transform="translate(8 8) scale(2)"
        fill="#fff"
        d="M8.5 2.687c.654-.689 1.782-.886 3.112-.752 1.234.124 2.503.523 3.388.893v9.923c-.918-.35-2.107-.692-3.287-.81-1.094-.111-2.278-.039-3.213.492zM8 1.783C7.015.936 5.587.81 4.287.94c-1.514.153-3.042.672-3.994 1.105A.5.5 0 0 0 0 2.5v11a.5.5 0 0 0 .707.455c.882-.4 2.303-.881 3.68-1.02 1.409-.142 2.59.087 3.223.877a.5.5 0 0 0 .78 0c.633-.79 1.814-1.019 3.222-.877 1.378.139 2.8.62 3.681 1.02A.5.5 0 0 0 16 13.5v-11a.5.5 0 0 0-.293-.455c-.952-.433-2.48-.952-3.994-1.105C10.413.809 8.985.936 8 1.783"
      />
    </svg>
  );
}

/** Mark plus wordmark. Use tone="dark" on light backgrounds and tone="light" on the blue hero. */
export default function Logo({
  tone = "dark",
  size = 40,
  className = "",
}: {
  tone?: "dark" | "light";
  size?: number;
  className?: string;
}) {
  const light = tone === "light";
  return (
    <span className={`d-inline-flex align-items-center gap-2 ${className}`}>
      <LogoMark size={size} />
      <span
        className={`tw:font-bold tw:tracking-tight tw:leading-none ${light ? "tw:text-white" : "tw:text-ink"}`}
        style={{ fontSize: Math.round(size * 0.46) }}
      >
        Learning{" "}
        <span style={{ color: light ? "#FBB040" : "var(--edu-brand)" }}>
          OS
        </span>
      </span>
    </span>
  );
}
