/**
 * Line icons in the brand orange, replacing the emoji.
 *
 * Emoji render differently on every platform and carry their own colours, so a
 * grid of them never looks designed. These inherit currentColor and share one
 * stroke weight, which is what makes a set read as a set.
 */

const PATHS = {
  books: (
    <>
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H19v15H6.5A2.5 2.5 0 0 0 4 20.5z" />
      <path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H19v3H6.5A2.5 2.5 0 0 1 4 20.5z" />
      <path d="M9 7h6" />
    </>
  ),
  electronics: (
    <>
      <rect x="3" y="5" width="18" height="12" rx="1.5" />
      <path d="M2 20h20" />
    </>
  ),
  furniture: (
    <>
      <path d="M6 10V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v5" />
      <path d="M5 10h14v5H5z" />
      <path d="M6 15v5M18 15v5" />
    </>
  ),
  kitchen: (
    <>
      <path d="M6 3v7a2 2 0 0 0 4 0V3M8 12v9" />
      <path d="M17 3c-1.5 1.5-2 3-2 5s.5 3 2 3v10" />
    </>
  ),
  tools: (
    <>
      <path d="M14.5 5.5a4 4 0 0 0 5.2 5.2l-7.6 7.6a2.5 2.5 0 0 1-3.5-3.5z" />
      <path d="M14.5 5.5 17 3" />
    </>
  ),
  sports: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" />
    </>
  ),
  party: (
    <>
      <path d="M4 20 9 8l7 7z" />
      <path d="M14 4v2M18 6l-1.5 1.5M20 11h-2" />
    </>
  ),
  other: (
    <>
      <path d="M3 8 12 3l9 5v8l-9 5-9-5z" />
      <path d="M3 8l9 5 9-5M12 13v10" />
    </>
  ),

  // interface
  walk: (
    <>
      <circle cx="13" cy="4" r="1.6" />
      <path d="M11 21l2-6-2.5-2.5L9 9l3.5-1.5L16 10l3 1" />
      <path d="M10.5 12.5 7 16l-1 5" />
    </>
  ),
  bike: (
    <>
      <circle cx="6" cy="17" r="3.5" />
      <circle cx="18" cy="17" r="3.5" />
      <path d="M6 17l4-8h5l3 8M9 9h5" />
    </>
  ),
  bus: (
    <>
      <rect x="4" y="4" width="16" height="13" rx="2" />
      <path d="M4 11h16M8 21v-2M16 21v-2" />
      <circle cx="8" cy="14.5" r=".8" fill="currentColor" stroke="none" />
      <circle cx="16" cy="14.5" r=".8" fill="currentColor" stroke="none" />
    </>
  ),
  car: (
    <>
      <path d="M4 16v3M20 16v3" />
      <path d="M3 16v-3l2-5h14l2 5v3z" />
      <circle cx="7.5" cy="16" r="1.4" />
      <circle cx="16.5" cy="16" r="1.4" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </>
  ),
  pin: (
    <>
      <path d="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11z" />
      <circle cx="12" cy="10" r="2.5" />
    </>
  ),
  chat: (
    <>
      <path d="M21 12a8 8 0 0 1-8 8H7l-4 3v-6a8 8 0 0 1 8-8h2a8 8 0 0 1 8 3z" />
    </>
  ),
  camera: (
    <>
      <path d="M3 8h3.5L8 5.5h8L17.5 8H21v11H3z" />
      <circle cx="12" cy="13.5" r="3.5" />
    </>
  ),
  recycle: (
    <>
      <path d="M7 19H5a2 2 0 0 1-1.7-3l1.6-2.7M12 3l2 3.4M17 19h2a2 2 0 0 0 1.7-3L15 6.4" />
      <path d="M9 5.5 7 9l3.5.5M20 13.5 18.5 17l-3.5-.5M5 19l2-3" />
    </>
  ),
};

// The Django Category rows still carry an emoji, so map on slug and fall back.
const BY_SLUG = {
  books: "books",
  electronics: "electronics",
  furniture: "furniture",
  kitchen: "kitchen",
  tools: "tools",
  sports: "sports",
  party: "party",
  other: "other",
};

export default function Icon({ name, slug, size = 22, strokeWidth = 1.6, style }) {
  const key = name || BY_SLUG[slug] || "other";
  const paths = PATHS[key];
  if (!paths) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      style={{ display: "block", ...style }}
    >
      {paths}
    </svg>
  );
}
