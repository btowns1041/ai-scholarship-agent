import { AlarmClock, BadgeDollarSign, ClipboardList, Sparkles } from "lucide-react";

const CARDS = [
  {
    key: "total_matches",
    label: "Total matches found",
    icon: Sparkles,
    format: (v) => v ?? 0,
    hint: "Scholarships scored against your profile",
  },
  {
    key: "pending_applications",
    label: "Pending applications",
    icon: ClipboardList,
    format: (v) => v ?? 0,
    hint: "Saved or in progress",
  },
  {
    key: "total_award_potential",
    label: "Total award potential",
    icon: BadgeDollarSign,
    format: (v) =>
      new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(v || 0),
    hint: "Excludes Not Interested",
  },
  {
    key: "upcoming_deadlines",
    label: "Upcoming deadlines",
    icon: AlarmClock,
    format: (v) => v ?? 0,
    hint: "Due within 14 days",
  },
];

export default function Dashboard({ metrics }) {
  return (
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {CARDS.map((card) => {
        const Icon = card.icon;
        return (
          <article
            key={card.key}
            className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-lg shadow-black/20 backdrop-blur"
          >
            <div className="flex items-start justify-between">
              <p className="text-sm text-slate-300">{card.label}</p>
              <span className="rounded-full bg-teal-400/10 p-2 text-teal-300">
                <Icon size={18} />
              </span>
            </div>
            <p className="mt-3 text-3xl font-semibold tracking-tight">
              {card.format(metrics?.[card.key])}
            </p>
            <p className="mt-1 text-xs text-slate-400">{card.hint}</p>
          </article>
        );
      })}
    </section>
  );
}
