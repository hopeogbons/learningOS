import { LogoMark } from "./Logo";

const motifs = [
  { x: 3, y: 8, size: 86, rotate: -13, opacity: 0.82 },
  { x: 31, y: 56, size: 72, rotate: 8, opacity: 0.68 },
  { x: 62, y: 21, size: 105, rotate: 17, opacity: 0.72 },
  { x: 89, y: 78, size: 88, rotate: -9, opacity: 0.74 },
  { x: 12, y: 33, size: 112, rotate: 11, opacity: 0.74 },
  { x: 47, y: 95, size: 76, rotate: 15, opacity: 0.68 },
  { x: 77, y: 44, size: 98, rotate: -7, opacity: 0.7 },
  { x: 22, y: 67, size: 83, rotate: 12, opacity: 0.76 },
  { x: 55, y: 13, size: 118, rotate: -15, opacity: 0.68 },
  { x: 96, y: 84, size: 92, rotate: -6, opacity: 0.75 },
  { x: 38, y: 27, size: 91, rotate: 14, opacity: 0.68 },
  { x: 70, y: 61, size: 115, rotate: -12, opacity: 0.7 },
  { x: 7, y: 94, size: 88, rotate: 6, opacity: 0.72 },
  { x: 54, y: 37, size: 108, rotate: -9, opacity: 0.74 },
  { x: 84, y: 72, size: 78, rotate: 10, opacity: 0.7 },
  { x: 24, y: 18, size: 103, rotate: -16, opacity: 0.68 },
  { x: 68, y: 89, size: 90, rotate: 9, opacity: 0.72 },
  { x: 98, y: 5, size: 110, rotate: -5, opacity: 0.7 },
  { x: 42, y: 75, size: 96, rotate: 13, opacity: 0.72 },
  { x: 15, y: 49, size: 82, rotate: -11, opacity: 0.68 },
  { x: 79, y: 29, size: 91, rotate: 7, opacity: 0.72 },
  { x: 34, y: 91, size: 107, rotate: -14, opacity: 0.7 },
];

/** Soft, asymmetric brain/circuit mark pattern for the matching mobile/desktop heroes. */
export default function LearningPattern() {
  return (
    <div className="learning-motif-pattern" aria-hidden="true">
      {motifs.map(({ x, y, size, rotate, opacity }, index) => (
        <span
          className="learning-motif"
          key={index}
          style={{
            insetInlineStart: `${x}%`,
            insetBlockStart: `${y}%`,
            opacity,
            transform: `rotate(${rotate}deg)`,
          }}
        >
          <LogoMark size={size} color="currentColor" />
        </span>
      ))}
    </div>
  );
}
