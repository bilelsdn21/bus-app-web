// Dot color -> tailwind classes + emoji, matching the Excel app's legend.
export const DOT = {
  green:  { bg: "bg-emerald-500", ring: "bg-emerald-100", label: "Plusieurs périodes", emoji: "🟢" },
  yellow: { bg: "bg-amber-400",   ring: "bg-amber-100",   label: "Matin",             emoji: "🌅" },
  orange: { bg: "bg-orange-500",  ring: "bg-orange-100",  label: "Soir",              emoji: "🌆" },
  purple: { bg: "bg-violet-500",  ring: "bg-violet-100",  label: "Nuit",              emoji: "🌙" },
  red:    { bg: "bg-rose-500",    ring: "bg-rose-100",    label: "Indisponible",      emoji: "🔴" },
};

export const fmtTND = (n) =>
  (n < 0 ? "-" : "") + Math.abs(Math.round(n)).toLocaleString("fr-FR") + " TND";
