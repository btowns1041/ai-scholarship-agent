import { useEffect, useState } from "react";
import { X } from "lucide-react";

const EMPTY = {
  full_name: "",
  major: "",
  gpa: 3.5,
  degree: "Undergraduate",
  year: "Junior",
  demographics: "",
  interests: "",
  citizenship: "US",
  state: "",
  financial_need: true,
};

export default function ProfileForm({ open, profile, saving, onClose, onSave }) {
  const [form, setForm] = useState(() => ({ ...EMPTY, ...(profile || {}) }));

  useEffect(() => {
    if (open) {
      setForm({ ...EMPTY, ...(profile || {}) });
    }
  }, [open, profile]);

  if (!open) return null;

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function submit(event) {
    event.preventDefault();
    onSave({
      ...form,
      gpa: Number(form.gpa),
      financial_need: Boolean(form.financial_need),
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/50 p-4">
      <form
        onSubmit={submit}
        className="h-full w-full max-w-md overflow-y-auto rounded-2xl border border-white/10 bg-ink-900 p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Student profile</h2>
            <p className="text-sm text-slate-400">Used by Claude to score every listing.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-white/10">
            <X size={18} />
          </button>
        </div>

        <div className="mt-5 space-y-3">
          <Field label="Full name">
            <input
              value={form.full_name}
              onChange={(e) => update("full_name", e.target.value)}
              className="input"
            />
          </Field>
          <Field label="Major">
            <input
              value={form.major}
              onChange={(e) => update("major", e.target.value)}
              className="input"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="GPA">
              <input
                type="number"
                min="0"
                max="4"
                step="0.01"
                value={form.gpa}
                onChange={(e) => update("gpa", e.target.value)}
                className="input"
              />
            </Field>
            <Field label="Year">
              <input
                value={form.year}
                onChange={(e) => update("year", e.target.value)}
                className="input"
              />
            </Field>
          </div>
          <Field label="Degree level">
            <select
              value={form.degree}
              onChange={(e) => update("degree", e.target.value)}
              className="input"
            >
              <option>High School</option>
              <option>Undergraduate</option>
              <option>Graduate</option>
              <option>Doctoral</option>
            </select>
          </Field>
          <Field label="Demographics">
            <input
              value={form.demographics}
              onChange={(e) => update("demographics", e.target.value)}
              placeholder="First-generation, underrepresented, ..."
              className="input"
            />
          </Field>
          <Field label="Interests">
            <input
              value={form.interests}
              onChange={(e) => update("interests", e.target.value)}
              className="input"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Citizenship">
              <input
                value={form.citizenship}
                onChange={(e) => update("citizenship", e.target.value)}
                className="input"
              />
            </Field>
            <Field label="State">
              <input
                value={form.state}
                onChange={(e) => update("state", e.target.value)}
                className="input"
              />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={Boolean(form.financial_need)}
              onChange={(e) => update("financial_need", e.target.checked)}
            />
            Demonstrate financial need
          </label>
        </div>

        <div className="mt-6 flex gap-3">
          <button
            type="submit"
            disabled={saving}
            className="flex-1 rounded-xl bg-teal-400 px-4 py-2 font-medium text-ink-950 disabled:opacity-60"
          >
            {saving ? "Saving..." : "Save and rescore"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-white/15 px-4 py-2 text-sm"
          >
            Cancel
          </button>
        </div>
      </form>
      <style>{`
        .input {
          width: 100%;
          border-radius: 0.75rem;
          border: 1px solid rgba(255,255,255,0.1);
          background: #07111f;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          outline: none;
        }
      `}</style>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-slate-300">{label}</span>
      {children}
    </label>
  );
}
