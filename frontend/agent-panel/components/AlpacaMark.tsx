/**
 * AlpacaMark — minimal alpaca/llama line-art SVG icon for the Paper Agent launcher.
 *
 * Designed by the implementor as a minimalist original icon when no suitable
 * open-source SVG was available under a permissive license. This icon draws
 * a simple alpaca face with the characteristic tall ears, a calm expression,
 * and a woolly crown — all in a restrained single-stroke style.
 *
 * License: MIT (same as the project).
 */

interface AlpacaMarkProps {
  size?: number;
  className?: string;
}

export function AlpacaMark({ size = 24, className = "" }: AlpacaMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-label="Paper Agent"
      role="img"
    >
      {/* Left ear */}
      <path
        d="M10 10c-1-2-2-5-1-6s3 1 4 3"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      {/* Right ear */}
      <path
        d="M22 10c1-2 2-5 1-6s-3 1-4 3"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      {/* Face outline */}
      <path
        d="M10 14c0-4 12-4 12 0v6c0 4-12 4-12 0z"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      {/* Woolly crown */}
      <path
        d="M11 13c0-1 2-2 5-2s5 1 5 2"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linecap="round"
        stroke-linejoin="round"
        opacity="0.7"
      />
      {/* Left eye */}
      <circle cx="13" cy="15" r="1.2" fill="currentColor" />
      {/* Right eye */}
      <circle cx="19" cy="15" r="1.2" fill="currentColor" />
      {/* Nose */}
      <path
        d="M15 17c0-0.6 2-0.6 2 0v1c0 0.6-2 0.6-2 0z"
        stroke="currentColor"
        stroke-width="1.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      {/* Gentle smile */}
      <path
        d="M14 19c1 0.5 3 0.5 4 0"
        stroke="currentColor"
        stroke-width="1.2"
        stroke-linecap="round"
      />
    </svg>
  );
}
