import brand from '../../../../brand.json'

/** Monogram in a ring-and-bearing frame; the letter comes from brand.json, so a rename follows. */
export function BrandMark({ size = 24 }: { size?: number }) {
  const initial = brand.productName.trim().charAt(0).toUpperCase()
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      role="img"
      aria-label={brand.productName}
      focusable="false"
    >
      <circle cx="12" cy="12" r="10.5" fill="none" stroke="var(--text-2)" strokeWidth="1.25" />
      <path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3" stroke="var(--text-2)" strokeWidth="1.25" />
      <rect
        x="17.25"
        y="3.25"
        width="3.5"
        height="3.5"
        fill="none"
        stroke="var(--signal)"
        strokeWidth="1.25"
      />
      <text
        x="12"
        y="16"
        textAnchor="middle"
        fontFamily="var(--font-mono)"
        fontWeight="500"
        fontSize="11.5"
        fill="var(--text)"
      >
        {initial}
      </text>
    </svg>
  )
}
