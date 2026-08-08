import { useState } from "react";
import { updateMyClub } from "../api/client";
import { useAuth } from "../context/AuthContext.jsx";

export default function Settings() {
  const { club, refreshClub } = useAuth();
  const [name, setName] = useState(club?.name ?? "");
  const [logoUrl, setLogoUrl] = useState(club?.logo_url ?? "");
  const [primaryColor, setPrimaryColor] = useState(club?.primary_color ?? "#059669");
  const [secondaryColor, setSecondaryColor] = useState(club?.secondary_color ?? "#111827");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateMyClub({
        name,
        logo_url: logoUrl || null,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
      });
      await refreshClub();
      setSaved(true);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto py-10 px-4">
      <h1 className="text-2xl font-bold text-white mb-1">Whitelabel instellingen</h1>
      <p className="text-sm text-gray-400 mb-6">Maak het platform helemaal van jouw club.</p>

      <form onSubmit={handleSubmit} className="space-y-4 bg-gray-800 rounded-lg p-4">
        <label className="flex flex-col text-sm text-gray-300">
          Clubnaam
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 bg-gray-900 text-white rounded-md px-3 py-2"
          />
        </label>
        <label className="flex flex-col text-sm text-gray-300">
          Logo URL
          <input
            type="text"
            value={logoUrl ?? ""}
            onChange={(e) => setLogoUrl(e.target.value)}
            placeholder="https://…"
            className="mt-1 bg-gray-900 text-white rounded-md px-3 py-2"
          />
        </label>
        <div className="flex gap-4">
          <label className="flex flex-col text-sm text-gray-300 flex-1">
            Primaire kleur
            <input
              type="color"
              value={primaryColor ?? "#059669"}
              onChange={(e) => setPrimaryColor(e.target.value)}
              className="mt-1 h-10 w-full bg-gray-900 rounded-md"
            />
          </label>
          <label className="flex flex-col text-sm text-gray-300 flex-1">
            Secundaire kleur
            <input
              type="color"
              value={secondaryColor ?? "#111827"}
              onChange={(e) => setSecondaryColor(e.target.value)}
              className="mt-1 h-10 w-full bg-gray-900 rounded-md"
            />
          </label>
        </div>

        {logoUrl && (
          <div className="flex items-center gap-3 pt-2">
            <img src={logoUrl} alt="logo preview" className="h-10 w-10 rounded object-contain bg-white" />
            <span className="text-sm text-gray-400">Logo preview</span>
          </div>
        )}

        {error && <p className="text-red-400 text-sm">{error}</p>}
        {saved && <p className="text-emerald-400 text-sm">Opgeslagen.</p>}

        <button
          type="submit"
          disabled={saving}
          style={{ backgroundColor: primaryColor }}
          className="text-white px-4 py-2 rounded-md disabled:opacity-50"
        >
          {saving ? "Bezig…" : "Opslaan"}
        </button>
      </form>
    </div>
  );
}
