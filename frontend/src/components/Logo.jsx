// Bestimetravel brand mark — a gold bus. Scales crisply at any size (SVG).
export default function Logo({ className = "h-10 w-10" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-label="Bestimetravel">
      <defs>
        <linearGradient id="bttGold" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fcd34d" />
          <stop offset="1" stopColor="#d97706" />
        </linearGradient>
      </defs>
      <rect x="3" y="4.5" width="18" height="12" rx="2.6" fill="url(#bttGold)" />
      <rect x="4.6" y="6.4" width="14.8" height="3.7" rx="1" fill="#dbeafe" />
      <line x1="9.3" y1="6.4" x2="9.3" y2="10.1" stroke="#b45309" strokeWidth="0.9" />
      <line x1="14" y1="6.4" x2="14" y2="10.1" stroke="#b45309" strokeWidth="0.9" />
      <circle cx="20.2" cy="12" r="0.7" fill="#fff7ed" />
      <circle cx="8" cy="17" r="2.1" fill="#1a3a5c" />
      <circle cx="8" cy="17" r="0.8" fill="#e2e8f0" />
      <circle cx="16" cy="17" r="2.1" fill="#1a3a5c" />
      <circle cx="16" cy="17" r="0.8" fill="#e2e8f0" />
    </svg>
  );
}
