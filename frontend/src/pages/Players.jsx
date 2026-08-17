import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  createPlayer,
  downloadImportTemplate,
  getPlayer,
  getSquadOverview,
  importPlayers,
  updatePlayer,
} from "../api/client";
import { useAuth } from "../context/AuthContext.jsx";

const POSITION_LABELS = {
  GK: "Doelman",
  CB: "Centrale verdediger",
  FB: "Flankverdediger",
  DM: "Verdedigende middenvelder",
  CM: "Centrale middenvelder",
  AM: "Aanvallende middenvelder",
  WNG: "Vleugelspeler",
  ST: "Spits",
};
const POSITION_ORDER = ["GK", "CB", "FB", "DM", "CM", "AM", "WNG", "ST"];

const DOMINANT_FOOT_LABELS = { left: "Links", right: "Rechts", both: "Beide" };

// Mirrors app/routers/team_readiness.py's ATTENTION_FLAG_TYPES — the exact
// flag set the Next Training "Belast/overbelast/geblesseerd" tile counts,
// so its ?filter=flagged link shows exactly that set here (deliberately
// excludes "underload", a Squad Overview 'reductie' signal, not a
// load-management concern for that tile).
const ATTENTION_FLAG_TYPES = new Set(["overload", "poor_recovery", "acwr_trending_up", "injured"]);

const STATUS_META = {
  fit: { label: "Fit", dot: "bg-emerald-500", badge: "bg-emerald-500/15 text-emerald-400", ring: "ring-emerald-500/30" },
  reductie: { label: "Reductie", dot: "bg-amber-500", badge: "bg-amber-500/15 text-amber-400", ring: "ring-amber-500/30" },
  overbelast: { label: "Overbelast", dot: "bg-red-500", badge: "bg-red-500/15 text-red-400", ring: "ring-red-500/30" },
  geen_data: { label: "Geen data", dot: "bg-gray-500", badge: "bg-gray-500/15 text-gray-400", ring: "ring-white/10" },
};

function initials(firstName, lastName) {
  return `${firstName?.[0] ?? ""}${lastName?.[0] ?? ""}`.toUpperCase();
}

const emptyEditForm = (p) => ({
  first_name: p.first_name ?? "",
  last_name: p.last_name ?? "",
  jersey_number: p.jersey_number ?? "",
  position: p.position ?? "",
  date_of_birth: p.date_of_birth ?? "",
  dominant_foot: p.dominant_foot ?? "",
  email: p.email ?? "",
  phone_number: p.phone_number ?? "",
});

export default function Players() {
  const { club } = useAuth();
  const rpeModuleActive = Boolean(club?.enabled_modules?.includes("rpe_wellness"));
  const [searchParams, setSearchParams] = useSearchParams();
  const flaggedOnly = searchParams.get("filter") === "flagged";

  const [squad, setSquad] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [positionFilter, setPositionFilter] = useState("ALL");

  const [showAddForm, setShowAddForm] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [jerseyNumber, setJerseyNumber] = useState("");
  const [position, setPosition] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [addSubmitting, setAddSubmitting] = useState(false);
  const [addError, setAddError] = useState(null);

  const [importResult, setImportResult] = useState(null);
  const [importError, setImportError] = useState(null);
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef(null);

  const [editPlayerId, setEditPlayerId] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [editLoading, setEditLoading] = useState(false);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState(null);

  const refresh = async () => {
    setLoading(true);
    try {
      setSquad(await getSquadOverview());
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const statusCounts = useMemo(() => {
    const counts = { fit: 0, reductie: 0, overbelast: 0, geen_data: 0 };
    for (const p of squad) counts[p.status] += 1;
    return counts;
  }, [squad]);

  const availablePositions = useMemo(() => {
    const present = new Set(squad.map((p) => p.position).filter(Boolean));
    return POSITION_ORDER.filter((pos) => present.has(pos));
  }, [squad]);

  const filteredSquad = useMemo(() => {
    let result = positionFilter === "ALL" ? squad : squad.filter((p) => p.position === positionFilter);
    if (flaggedOnly) {
      result = result.filter((p) => (p.flag_types ?? []).some((t) => ATTENTION_FLAG_TYPES.has(t)));
    }
    return result;
  }, [squad, positionFilter, flaggedOnly]);

  const clearFlaggedFilter = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("filter");
    setSearchParams(next);
  };

  const openEditForm = async (p) => {
    setEditPlayerId(p.id);
    setEditForm(null);
    setEditError(null);
    setEditLoading(true);
    try {
      // Squad Overview rows don't carry date_of_birth/dominant_foot/contact
      // fields (those aren't needed for the readiness display) — fetch the
      // full player record so the edit form never silently blanks them out.
      const full = await getPlayer(p.id);
      setEditForm(emptyEditForm(full));
    } catch (err) {
      setEditError(err.response?.data?.detail ?? err.message);
    } finally {
      setEditLoading(false);
    }
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    setEditSubmitting(true);
    setEditError(null);
    try {
      await updatePlayer(editPlayerId, {
        first_name: editForm.first_name,
        last_name: editForm.last_name,
        jersey_number: editForm.jersey_number === "" ? null : Number(editForm.jersey_number),
        position: editForm.position === "" ? null : editForm.position,
        date_of_birth: editForm.date_of_birth === "" ? null : editForm.date_of_birth,
        dominant_foot: editForm.dominant_foot === "" ? null : editForm.dominant_foot,
        email: editForm.email === "" ? null : editForm.email,
        phone_number: editForm.phone_number === "" ? null : editForm.phone_number,
      });
      setEditPlayerId(null);
      setEditForm(null);
      await refresh();
    } catch (err) {
      setEditError(err.response?.data?.detail ?? err.message);
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleAddPlayer = async (e) => {
    e.preventDefault();
    setAddSubmitting(true);
    setAddError(null);
    try {
      await createPlayer({
        first_name: firstName,
        last_name: lastName,
        jersey_number: jerseyNumber === "" ? null : Number(jerseyNumber),
        position: position === "" ? null : position,
        date_of_birth: dateOfBirth === "" ? null : dateOfBirth,
        email: email || null,
        phone_number: phoneNumber || null,
      });
      setFirstName("");
      setLastName("");
      setJerseyNumber("");
      setPosition("");
      setDateOfBirth("");
      setEmail("");
      setPhoneNumber("");
      setShowAddForm(false);
      await refresh();
    } catch (err) {
      setAddError(err.response?.data?.detail ?? err.message);
    } finally {
      setAddSubmitting(false);
    }
  };

  const handleDownloadTemplate = async () => {
    const blob = await downloadImportTemplate();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "spelers_import_sjabloon.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  };

  const handleImportFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportError(null);
    setImportResult(null);
    try {
      const result = await importPlayers(file);
      setImportResult(result);
      await refresh();
    } catch (err) {
      setImportError(err.response?.data?.detail ?? err.message);
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-12 px-4">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Squad Overview</h1>
          <p className="text-sm text-gray-400">
            Spelersgegevens en statusoverzicht op basis van afgelegde kilometers uit de voorbije 28 dagen
            {rpeModuleActive ? ", aangevuld met RPE en wellness-gegevens." : "."} MAS-testen verlopen via de
            kalender, RPE-invoer via het RPE &amp; Wellness-tabblad.
          </p>
        </div>
        <button
          onClick={() => setShowAddForm((v) => !v)}
          className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium shrink-0"
        >
          {showAddForm ? "Annuleren" : "+ Speler toevoegen"}
        </button>
      </div>

      {flaggedOnly && (
        <div className="bg-amber-500/10 border border-amber-500/30 text-amber-300 rounded-2xl px-5 py-3.5 mb-6 text-sm flex items-center justify-between gap-3 flex-wrap">
          <span>
            Gefilterd op belast / overbelast / geblesseerd spelers (vanuit de Next Training-tegel).
          </span>
          <button onClick={clearFlaggedFilter} className="underline hover:opacity-80 shrink-0">
            Filter wissen
          </button>
        </div>
      )}

      {showAddForm && (
        <form onSubmit={handleAddPlayer} className="bg-gray-900/60 border border-white/10 rounded-2xl p-6 mb-6 space-y-4 shadow-xl shadow-black/20">
          <div className="grid grid-cols-2 gap-3">
            <input
              required
              placeholder="Voornaam"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
            />
            <input
              required
              placeholder="Naam"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
            />
            <input
              type="number"
              min="0"
              max="99"
              placeholder="Rugnummer"
              value={jerseyNumber}
              onChange={(e) => setJerseyNumber(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
            />
            <select
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
            >
              <option value="">Positie (optioneel)</option>
              {POSITION_ORDER.map((pos) => (
                <option key={pos} value={pos}>
                  {pos} · {POSITION_LABELS[pos]}
                </option>
              ))}
            </select>
            <label className="flex flex-col text-gray-400 text-xs gap-1">
              Geboortedatum
              <input
                type="date"
                value={dateOfBirth}
                onChange={(e) => setDateOfBirth(e.target.value)}
                className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
              />
            </label>
            <input
              type="email"
              placeholder="E-mailadres"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
            />
            <input
              placeholder="Telefoonnummer"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm col-span-2 focus:outline-none focus:ring-2 ring-brand"
            />
          </div>
          {addError && <p className="text-red-400 text-sm">{addError}</p>}
          <button
            type="submit"
            disabled={addSubmitting}
            className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {addSubmitting ? "Bezig…" : "Toevoegen"}
          </button>
        </form>
      )}

      <div className="bg-gray-900/60 border border-white/10 rounded-2xl p-6 mb-6 shadow-xl shadow-black/20">
        <h2 className="text-white font-semibold mb-1">Bulk import</h2>
        <p className="text-sm text-gray-400 mb-3">
          Download het sjabloon, vul de gegevens in (rugnummer, naam, voornaam, e-mailadres,
          telefoonnummer) en upload het opnieuw om alle spelers in één keer in te laden.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleDownloadTemplate}
            className="bg-white/5 hover:bg-white/10 border border-white/10 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            Download sjabloon (.xlsx)
          </button>
          <label className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium cursor-pointer">
            {importing ? "Bezig met importeren…" : "Upload ingevuld sjabloon"}
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xlsm"
              onChange={handleImportFile}
              disabled={importing}
              className="hidden"
            />
          </label>
        </div>
        {importError && <p className="text-red-400 text-sm mt-3">{importError}</p>}
        {importResult && (
          <div className="text-sm mt-3 text-gray-300">
            <p>
              {importResult.created} speler(s) aangemaakt, {importResult.skipped} rij(en) overgeslagen.
            </p>
            {importResult.errors.length > 0 && (
              <ul className="list-disc list-inside text-red-400 mt-1">
                {importResult.errors.map((err) => (
                  <li key={err.row}>
                    Rij {err.row}: {err.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {loading && <p className="text-gray-400">Laden…</p>}
      {error && <p className="text-red-400">{error}</p>}

      {!loading && !error && squad.length === 0 && (
        <div className="bg-gray-900/60 border border-white/10 rounded-2xl p-8 text-center text-gray-500 shadow-xl shadow-black/20">
          Nog geen spelers. Voeg er een toe of importeer het sjabloon.
        </div>
      )}

      {!loading && !error && squad.length > 0 && (
        <>
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {["fit", "reductie", "overbelast"].map((status) => (
              <span
                key={status}
                className={`inline-flex items-center gap-1.5 ${STATUS_META[status].badge} px-3 py-1.5 rounded-full text-xs font-semibold`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${STATUS_META[status].dot}`} />
                {statusCounts[status]} {STATUS_META[status].label}
              </span>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2 mb-6">
            <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium mr-1">Positie</span>
            <button
              onClick={() => setPositionFilter("ALL")}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
                positionFilter === "ALL"
                  ? "nav-active-brand border-transparent"
                  : "border-white/10 text-gray-400 hover:bg-white/5"
              }`}
            >
              Alle
            </button>
            {availablePositions.map((pos) => (
              <button
                key={pos}
                onClick={() => setPositionFilter(pos)}
                title={POSITION_LABELS[pos]}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
                  positionFilter === pos
                    ? "nav-active-brand border-transparent"
                    : "border-white/10 text-gray-400 hover:bg-white/5"
                }`}
              >
                {pos}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredSquad.map((p) => {
              const meta = STATUS_META[p.status];
              const isEditing = editPlayerId === p.id;
              return (
                <div
                  key={p.id}
                  className={`bg-gray-900/60 border border-white/10 rounded-2xl p-4 shadow-xl shadow-black/20 ring-1 ${meta.ring}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`h-10 w-10 shrink-0 rounded-full flex items-center justify-center text-sm font-bold ${meta.badge}`}>
                        {initials(p.first_name, p.last_name)}
                      </div>
                      <div className="min-w-0">
                        <p className="text-white font-semibold truncate">
                          {p.first_name} {p.last_name}
                        </p>
                        <p className="text-xs text-gray-500 truncate" title={p.position ? POSITION_LABELS[p.position] : undefined}>
                          {p.jersey_number != null ? `#${p.jersey_number}` : "—"}
                          {p.position ? ` · ${p.position}` : ""}
                        </p>
                      </div>
                    </div>
                    <span className={`shrink-0 px-2.5 py-1 rounded-full text-[11px] font-semibold ${meta.badge}`}>
                      {meta.label}
                    </span>
                  </div>

                  <div className="text-xs text-gray-400 mb-3">
                    {p.status === "geen_data" ? (
                      "Nog geen belastingsgegevens."
                    ) : (
                      <>
                        {p.acwr != null && <span>Km-ACWR {p.acwr}</span>}
                        {rpeModuleActive && p.acwr != null && (p.latest_rpe != null || p.latest_wellness != null) && (
                          <span> · </span>
                        )}
                        {rpeModuleActive && p.latest_rpe != null && <span>RPE {p.latest_rpe}</span>}
                        {rpeModuleActive && p.latest_rpe != null && p.latest_wellness != null && <span> · </span>}
                        {rpeModuleActive && p.latest_wellness != null && <span>Wellness {p.latest_wellness}/5</span>}
                      </>
                    )}
                    {p.flags.length > 0 && (
                      <ul className="mt-1.5 space-y-0.5">
                        {p.flags.map((detail, i) => (
                          <li key={i} className="text-[11px] text-gray-500">
                            {detail}
                            {rpeModuleActive && p.flag_sources?.[i] && (
                              <span className="text-gray-600"> ({p.flag_sources[i]})</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <button
                    onClick={() => (isEditing ? setEditPlayerId(null) : openEditForm(p))}
                    className="text-brand hover:opacity-80 text-xs font-medium"
                  >
                    {isEditing ? "Sluiten" : "Bewerken"}
                  </button>

                  {isEditing && editLoading && <p className="text-gray-500 text-xs mt-3 pt-3 border-t border-white/10">Laden…</p>}
                  {isEditing && editError && !editForm && <p className="text-red-400 text-xs mt-3 pt-3 border-t border-white/10">{editError}</p>}

                  {isEditing && editForm && (
                    <form onSubmit={handleSaveEdit} className="mt-3 pt-3 border-t border-white/10 space-y-2.5 text-sm">
                      <div className="grid grid-cols-2 gap-2.5">
                        <input
                          required
                          placeholder="Voornaam"
                          value={editForm.first_name}
                          onChange={(e) => setEditForm((f) => ({ ...f, first_name: e.target.value }))}
                          className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                        />
                        <input
                          required
                          placeholder="Naam"
                          value={editForm.last_name}
                          onChange={(e) => setEditForm((f) => ({ ...f, last_name: e.target.value }))}
                          className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                        />
                        <input
                          type="number"
                          min="0"
                          max="99"
                          placeholder="Rugnummer"
                          value={editForm.jersey_number}
                          onChange={(e) => setEditForm((f) => ({ ...f, jersey_number: e.target.value }))}
                          className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                        />
                        <select
                          value={editForm.position}
                          onChange={(e) => setEditForm((f) => ({ ...f, position: e.target.value }))}
                          className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                        >
                          <option value="">Positie</option>
                          {POSITION_ORDER.map((pos) => (
                            <option key={pos} value={pos}>
                              {pos} · {POSITION_LABELS[pos]}
                            </option>
                          ))}
                        </select>
                        <label className="flex flex-col text-gray-400 text-[10px] gap-1">
                          Geboortedatum
                          <input
                            type="date"
                            value={editForm.date_of_birth}
                            onChange={(e) => setEditForm((f) => ({ ...f, date_of_birth: e.target.value }))}
                            className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                          />
                        </label>
                        <select
                          value={editForm.dominant_foot}
                          onChange={(e) => setEditForm((f) => ({ ...f, dominant_foot: e.target.value }))}
                          className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                        >
                          <option value="">Voorkeursvoet</option>
                          {Object.entries(DOMINANT_FOOT_LABELS).map(([value, label]) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                        <input
                          type="email"
                          placeholder="E-mailadres"
                          value={editForm.email}
                          onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                          className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs col-span-2 focus:outline-none focus:ring-2 ring-brand"
                        />
                        <input
                          placeholder="Telefoonnummer"
                          value={editForm.phone_number}
                          onChange={(e) => setEditForm((f) => ({ ...f, phone_number: e.target.value }))}
                          className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs col-span-2 focus:outline-none focus:ring-2 ring-brand"
                        />
                      </div>
                      {editError && <p className="text-red-400 text-xs">{editError}</p>}
                      <button
                        type="submit"
                        disabled={editSubmitting}
                        className="btn-brand text-white px-4 py-2 rounded-lg text-sm font-medium w-full disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {editSubmitting ? "Bezig…" : "Opslaan"}
                      </button>
                    </form>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
