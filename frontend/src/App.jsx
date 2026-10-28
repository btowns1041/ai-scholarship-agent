import { useCallback, useEffect, useState } from "react";
import { GraduationCap, RefreshCw, Search, UserRound } from "lucide-react";
import Dashboard from "./components/Dashboard.jsx";
import ProfileForm from "./components/ProfileForm.jsx";
import ScholarshipList from "./components/ScholarshipList.jsx";
import {
  fetchMetrics,
  fetchProfile,
  fetchScholarships,
  rescore,
  saveProfile,
  scrapeAndEvaluate,
  updateStatus,
} from "./api.js";

const DEFAULT_URLS = "";

export default function App() {
  const [metrics, setMetrics] = useState(null);
  const [scholarships, setScholarships] = useState([]);
  const [profile, setProfile] = useState(null);
  const [sortBy, setSortBy] = useState("score");
  const [statusFilter, setStatusFilter] = useState("");
  const [urls, setUrls] = useState(DEFAULT_URLS);
  const [loading, setLoading] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    const [nextScholarships, nextMetrics, nextProfile] = await Promise.all([
      fetchScholarships(sortBy, statusFilter),
      fetchMetrics(),
      fetchProfile(),
    ]);
    setScholarships(nextScholarships);
    setMetrics(nextMetrics);
    setProfile(nextProfile);
  }, [sortBy, statusFilter]);

  useEffect(() => {
    refresh().catch((err) => setError(err.message || "Failed to load data"));
  }, [refresh]);

  async function runDiscovery() {
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const parsedUrls = urls
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      const result = await scrapeAndEvaluate({
        urls: parsedUrls,
        use_demo_fallback: true,
        max_items: 20,
      });
      setNotice(
        result.source === "demo"
          ? `Loaded ${result.count} demo scholarships (live pages returned no listings).`
          : `Scored ${result.count} scholarships from live pages.`
      );
      await refresh();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Discovery failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleStatus(id, status) {
    await updateStatus(id, status);
    await refresh();
  }

  async function handleSaveProfile(nextProfile) {
    setSavingProfile(true);
    setError("");
    try {
      await saveProfile(nextProfile);
      if (scholarships.length) {
        await rescore();
      }
      setProfileOpen(false);
      setNotice("Profile saved. Existing scholarships were rescored.");
      await refresh();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Could not save profile");
    } finally {
      setSavingProfile(false);
    }
  }

  return (
    <div className="mx-auto min-h-screen max-w-7xl px-4 py-8 sm:px-6">
      <header className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="mb-2 inline-flex items-center gap-2 rounded-full border border-teal-300/20 bg-teal-400/10 px-3 py-1 text-xs font-medium text-teal-200">
            <GraduationCap size={14} /> AI scholarship discovery
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Find, score, and track scholarships
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
            Playwright collects listings, Claude scores them against your profile, and this
            dashboard keeps deadlines, award potential, and application status in one place.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setProfileOpen(true)}
          className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm hover:bg-white/10"
        >
          <UserRound size={16} /> Edit profile
        </button>
      </header>

      <div className="mb-6 rounded-2xl border border-white/10 bg-white/5 p-4">
        <label className="text-sm font-medium text-slate-200">
          Target listing URLs (optional, one per line)
        </label>
        <textarea
          value={urls}
          onChange={(e) => setUrls(e.target.value)}
          rows={3}
          placeholder="https://example.edu/scholarships"
          className="mt-2 w-full rounded-xl border border-white/10 bg-ink-900 px-3 py-2 text-sm outline-none ring-teal-400/30 focus:ring-2"
        />
        <div className="mt-3 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={runDiscovery}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl bg-teal-400 px-4 py-2 text-sm font-semibold text-ink-950 disabled:opacity-60"
          >
            <Search size={16} />
            {loading ? "Scraping and scoring..." : "Scrape and evaluate"}
          </button>
          <button
            type="button"
            onClick={() => refresh()}
            className="inline-flex items-center gap-2 rounded-xl border border-white/15 px-4 py-2 text-sm"
          >
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
        {notice && <p className="mt-3 text-sm text-teal-200">{notice}</p>}
        {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}
      </div>

      <Dashboard metrics={metrics} />
      <div className="mt-6">
        <ScholarshipList
          scholarships={scholarships}
          sortBy={sortBy}
          onSortChange={setSortBy}
          statusFilter={statusFilter}
          onStatusFilter={setStatusFilter}
          onStatusUpdate={handleStatus}
        />
      </div>

      <ProfileForm
        open={profileOpen}
        profile={profile}
        saving={savingProfile}
        onClose={() => setProfileOpen(false)}
        onSave={handleSaveProfile}
      />
    </div>
  );
}
