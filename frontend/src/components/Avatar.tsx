import Image from "next/image";
import { LayoutGrid } from "lucide-react";

/**
 * Learner avatar slot.
 * With no `src` it shows a grid icon placeholder. Pass a photo URL to replace it:
 *   <Avatar src={user.photoUrl} size={84} />
 * The name is always rendered next to the avatar, so the image itself is decorative.
 */
export default function Avatar({
  src,
  size = 84,
  tone = "onDark",
  className = "",
}: {
  src?: string | null;
  size?: number;
  tone?: "onDark" | "onLight";
  className?: string;
}) {
  const ring =
    tone === "onDark"
      ? "tw:border-4 tw:border-white/90 tw:shadow-lg"
      : "tw:border tw:border-brand-100";
  const base = `tw:shrink-0 tw:rounded-full ${ring} ${className}`;

  if (src) {
    return (
      <Image
        src={src}
        alt=""
        width={size}
        height={size}
        unoptimized
        className={`${base} tw:object-cover`}
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <span
      aria-hidden="true"
      className={`tw:grid tw:place-items-center tw:bg-brand-50 tw:text-brand-600 ${base}`}
      style={{ width: size, height: size }}
    >
      <LayoutGrid size={Math.round(size * 0.44)} strokeWidth={1.8} />
    </span>
  );
}
