/** Standalone vector traced from the supplied brain/circuit mark. No tile or background. */
export function LogoMark({ size = 40, className, color = "var(--edu-brand)" }: {
  size?: number;
  className?: string;
  color?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="20 22.5 460 460" aria-hidden="true" className={className} style={{ color }}>
<path fill="currentColor" fillRule="evenodd" d="M235 252V104C235 66 220 47 190 47C152 44 122 72 106 105C113 105 119 106 124 108C129 111 126 120 120 120C87 112 53 137 52 173C50 194 62 211 72 223C77 230 68 236 62 230L47 212C21 241 27 294 65 326C58 353 65 376 86 391C99 400 111 399 129 397C138 397 138 409 131 411L119 414C126 443 157 460 188 460C217 460 235 442 235 416V386C225 375 219 368 210 361C203 353 212 344 219 351L235 365V266C211 270 188 265 176 245C169 235 180 228 186 237C197 252 213 257 235 252Z M179 95C173 98 176 104 178 110C186 138 170 159 145 161C132 162 121 159 115 153C107 147 99 157 107 164C119 175 138 178 155 173C166 194 185 202 209 201C218 201 217 187 209 188C190 190 177 182 168 167C192 152 203 125 187 96C185 92 182 91 179 95Z M133 215C126 219 119 237 119 251C106 247 92 250 82 257C75 264 83 272 90 267C110 255 127 266 133 285C143 310 122 330 108 335C99 339 107 350 115 345C139 333 155 308 147 284C142 271 132 266 132 250C132 239 137 228 142 223C148 215 139 210 133 215Z M207 308C181 308 160 326 158 351C155 372 167 391 188 402C198 408 202 396 194 391C175 381 168 368 171 350C173 334 188 320 208 320C216 320 218 308 207 308Z"/>
<g fill="none" stroke="currentColor" strokeWidth="13" strokeLinecap="round" strokeLinejoin="round"><path d="M398 120C389 80 347 50 312 53C274 49 256 69 256 106V398C256 432 277 454 307 454C343 455 363 434 371 397C411 395 438 359 427 315C463 294 469 242 440 208C457 171 430 118 398 120Z"/><path d="M375 122C404 113 427 128 438 149 M440 208L424 221 M371 397L363 397 M256 213H293L326 180H366 M256 257H337 M256 295H298L333 341H360 M331 61L313 86V114 M312 409L272 438 M256 389C262 373 270 357 282 351"/><circle cx="313" cy="132" r="15"/><circle cx="384" cy="180" r="15"/><circle cx="355" cy="257" r="15"/><circle cx="378" cy="341" r="15"/><circle cx="316" cy="395" r="15"/></g>
    </svg>
  );
}

/** Mark plus wordmark, with a light tone for the green hero. */
export default function Logo({ tone = "dark", size = 40, className = "" }: {
  tone?: "dark" | "light";
  size?: number;
  className?: string;
}) {
  const light = tone === "light";
  return (
    <span className={`d-inline-flex align-items-center gap-2 ${className}`}>
      <LogoMark size={size} color={light ? "#ffffff" : "var(--edu-brand)"} />
      <span className={`tw:font-bold tw:tracking-tight tw:leading-none ${light ? "tw:text-white" : "tw:text-ink"}`} style={{ fontSize: Math.round(size * 0.46) }}>
        Learning <span style={{ color: light ? "#b0d6cd" : "var(--edu-brand)" }}>OS</span>
      </span>
    </span>
  );
}
