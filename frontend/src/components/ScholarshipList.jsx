import { useMemo, useState } from "react";
import { ChevronDown, ExternalLink, Search } from "lucide-react";

const STATUSES = ["Saved", "In Progress", "Submitted", "Not Interested"];

function scoreTone(score) {
  if (score >= 80) return "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30";
  if (score >= 50) return "bg-amber-500/15 text-amber-300 ring-amber-400/30";
  return "bg-rose-500/15 text-rose-300 ring-rose-400/30";
}

function daysUntil(deadline) {
  if (!deadline) return null;
  const parsed = Date.parse(deadline);
  if (Number.isNaN(parsed)) return null;
  return Math.ceil((parsed - Date.now()) / (1000 * 60 * 60 * 24));
}

export default function ScholarshipList({
  scholarships,
  sortBy,
  onSortChange,
  statusFilter,
  onStatusFilter,
  onStatusUpdate,
}) {
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return scholarships;
    return scholarships.filter((item) =>
      [item.title, item.provider, item.eligibility_summary, item.ai_rationale]
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }, [scholarships, query]);

  return (
    <section className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-lg shadow-black/20">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Matched scholarships</h2>
          <p className="text-sm text-slate-400">
            Sorted by fit score by default. Expand a row for Claude’s rationale.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search title, provider, rationale"
              className="w-full rounded-xl border border-white/10 bg-ink-900 py-2 pl-9 pr-3 text-sm outline-none ring-teal-400/40 placeholder:text-slate-500 focus:ring-2 sm:w-72"
            />
          </label>
          <select
            value={sortBy}
            onChange={(e) => onSortChange(e.target.value)}
            className="rounded-xl border border-white/10 bg-ink-900 px-3 py-2 text-sm"
          >
            <option value="score">Highest match score</option>
            <option value="deadline">Soonest deadline</option>
            <option value="amount">Largest award</option>
            <option value="status">Status</option>
            <option value="newest">Newest</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => onStatusFilter(e.target.value)}
            className="rounded-xl border border-white/10 bg-ink-900 px-3 py-2 text-sm"
          >
            <option value="">All statuses</option>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-3 py-2">Scholarship</th>
              <th className="px-3 py-2">Award</th>
              <th className="px-3 py-2">Deadline</th>
              <th className="px-3 py-2">Match</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-10 text-center text-slate-400">
                  No scholarships yet. Run a discovery pass to populate this list.
                </td>
              </tr>
            )}
            {filtered.map((item) => {
              const dueIn = daysUntil(item.deadline);
              const urgent = dueIn !== null && dueIn >= 0 && dueIn <= 14;
              const open = openId === item.id;
              return (
                <tr key={item.id} className="border-t border-white/10 align-top">
                  <td className="px-3 py-4">
                    <button
                      type="button"
                      onClick={() => setOpenId(open ? null : item.id)}
                      className="flex items-start gap-2 text-left"
                    >
                      <ChevronDown
                        className={`mt-0.5 h-4 w-4 shrink-0 text-slate-400 transition ${open ? "rotate-0" : "-rotate-90"}`}
                      />
                      <span>
                        <span className="block font-medium text-white">{item.title}</span>
                        <span className="block text-xs text-slate-400">{item.provider}</span>
                      </span>
                    </button>
                    {open && (
                      <div className="mt-3 space-y-2 rounded-xl bg-black/20 p-3 text-slate-300">
                        <p>
                          <span className="font-medium text-teal-200">AI rationale: </span>
                          {item.ai_rationale || "No rationale stored."}
                        </p>
                        <p className="text-xs leading-5 text-slate-400">
                          {item.eligibility_summary}
                        </p>
                        {item.url && (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-teal-300 hover:underline"
                          >
                            Open listing <ExternalLink size={12} />
                          </a>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-4 font-semibold text-teal-200">
                    {item.award_amount || "—"}
                  </td>
                  <td className="px-3 py-4">
                    <span className={urgent ? "rounded-md bg-orange-500/20 px-2 py-1 text-orange-200" : ""}>
                      {item.deadline || "Unknown"}
                      {urgent ? ` · ${dueIn}d` : ""}
                    </span>
                  </td>
                  <td className="px-3 py-4">
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${scoreTone(item.match_score || 0)}`}>
                      {item.match_score ?? 0}
                    </span>
                  </td>
                  <td className="px-3 py-4">
                    <select
                      value={item.status || "Saved"}
                      onChange={(e) => onStatusUpdate(item.id, e.target.value)}
                      className="rounded-lg border border-white/10 bg-ink-900 px-2 py-1 text-xs"
                    >
                      {STATUSES.map((status) => (
                        <option key={status} value={status}>
                          {status}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
