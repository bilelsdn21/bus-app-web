// The Analyse page is paused while we refine the source data for precise results.
// Re-enable by restoring the previous rentability implementation from git history.
export default function AnalyticsView() {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-4 text-lg font-extrabold text-[#1a3a5c] sm:text-2xl">📈 Analyse</h1>

      <div className="rounded-3xl bg-white p-8 text-center shadow-lg ring-1 ring-slate-200 sm:p-12">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 text-3xl ring-1 ring-amber-100">
          🔧
        </div>
        <h2 className="mt-5 text-xl font-extrabold text-[#1a3a5c]">Analyse en préparation</h2>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-slate-500">
          Nous vérifions et affinons actuellement vos données afin de garantir une analyse
          <b className="text-slate-700"> précise et fiable </b>
          de la rentabilité de chaque véhicule.
        </p>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate-500">
          Cette page sera disponible très prochainement. Merci de votre patience. 🙏
        </p>

        <div className="mx-auto mt-6 inline-flex items-center gap-2 rounded-full bg-amber-50 px-4 py-2 text-xs font-bold text-amber-700 ring-1 ring-amber-100">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500" />
          </span>
          Bientôt disponible
        </div>
      </div>
    </div>
  );
}
