import { Fragment, useEffect, useRef, useState } from "react";
import {
  createPlayer,
  downloadImportTemplate,
  getMasTestProtocols,
  importPlayers,
  listPlayers,
  recordMasTest,
} from "../api/client";

export default function Players() {
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [protocols, setProtocols] = useState([]);
  const [testPlayerId, setTestPlayerId] = useState(null);
  const [testProtocolKey, setTestProtocolKey] = useState("");
  const [testRawResult, setTestRawResult] = useState("");
  const [testDate, setTestDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [testSubmitting, setTestSubmitting] = useState(false);
  const [testError, setTestError] = useState(null);
  const [testConfirmation, setTestConfirmation] = useState(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [jerseyNumber, setJerseyNumber] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [addSubmitting, setAddSubmitting] = useState(false);

  const [importResult, setImportResult] = useState(null);
  const [importError, setImportError] = useState(null);
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef(null);

  const refresh = async () => {
    setLoading(true);
    try {
      setPlayers(await listPlayers());
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    getMasTestProtocols()
      .then((result) => {
        setProtocols(result);
        if (result.length > 0) setTestProtocolKey(result[0].key);
      })
      .catch(() => {});
  }, []);

  const openTestForm = (playerId) => {
    setTestPlayerId(playerId);
    setTestRawResult("");
    setTestDate(new Date().toISOString().slice(0, 10));
    setTestError(null);
    setTestConfirmation(null);
  };

  const handleRecordMasTest = async (e) => {
    e.preventDefault();
    setTestSubmitting(true);
    setTestError(null);
    try {
      const result = await recordMasTest({
        player_id: testPlayerId,
        protocol_key: testProtocolKey,
        raw_result_kmh: Number(testRawResult),
        test_date: testDate,
      });
      setTestConfirmation(
        `MAS-score ${result.mas_kmh} km/u opgeslagen. Kalender bijgewerkt (${result.calendar_events_synced} testmoment(en)).`
      );
    } catch (err) {
      setTestError(err.response?.data?.detail ?? err.message);
    } finally {
      setTestSubmitting(false);
    }
  };

  const handleAddPlayer = async (e) => {
    e.preventDefault();
    setAddSubmitting(true);
    try {
      await createPlayer({
        first_name: firstName,
        last_name: lastName,
        jersey_number: jerseyNumber === "" ? null : Number(jerseyNumber),
        email: email || null,
        phone_number: phoneNumber || null,
      });
      setFirstName("");
      setLastName("");
      setJerseyNumber("");
      setEmail("");
      setPhoneNumber("");
      setShowAddForm(false);
      await refresh();
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
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
    <div className="max-w-3xl mx-auto py-10 px-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Spelers</h1>
          <p className="text-sm text-gray-400">Beheer je spelersgroep, individueel of in bulk.</p>
        </div>
        <button
          onClick={() => setShowAddForm((v) => !v)}
          className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-md text-sm"
        >
          {showAddForm ? "Annuleren" : "+ Speler toevoegen"}
        </button>
      </div>

      {showAddForm && (
        <form onSubmit={handleAddPlayer} className="bg-gray-800 rounded-lg p-4 mb-6 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input
              required
              placeholder="Voornaam"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="bg-gray-900 text-white rounded-md px-3 py-2 text-sm"
            />
            <input
              required
              placeholder="Naam"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="bg-gray-900 text-white rounded-md px-3 py-2 text-sm"
            />
            <input
              type="number"
              min="0"
              max="99"
              placeholder="Rugnummer"
              value={jerseyNumber}
              onChange={(e) => setJerseyNumber(e.target.value)}
              className="bg-gray-900 text-white rounded-md px-3 py-2 text-sm"
            />
            <input
              type="email"
              placeholder="E-mailadres"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-gray-900 text-white rounded-md px-3 py-2 text-sm"
            />
            <input
              placeholder="Telefoonnummer"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              className="bg-gray-900 text-white rounded-md px-3 py-2 text-sm col-span-2"
            />
          </div>
          <button
            type="submit"
            disabled={addSubmitting}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-md text-sm"
          >
            {addSubmitting ? "Bezig…" : "Toevoegen"}
          </button>
        </form>
      )}

      <div className="bg-gray-800 rounded-lg p-4 mb-6">
        <h2 className="text-white font-semibold mb-1">Bulk import</h2>
        <p className="text-sm text-gray-400 mb-3">
          Download het sjabloon, vul de gegevens in (rugnummer, naam, voornaam, e-mailadres,
          telefoonnummer) en upload het opnieuw om alle spelers in één keer in te laden.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleDownloadTemplate}
            className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-md text-sm"
          >
            Download sjabloon (.xlsx)
          </button>
          <label className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-md text-sm cursor-pointer">
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
      {!loading && !error && (
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm text-left text-gray-300">
            <thead className="bg-gray-700 text-gray-200">
              <tr>
                <th className="px-4 py-2">#</th>
                <th className="px-4 py-2">Naam</th>
                <th className="px-4 py-2">E-mailadres</th>
                <th className="px-4 py-2">Telefoonnummer</th>
                <th className="px-4 py-2">MAS-test</th>
              </tr>
            </thead>
            <tbody>
              {players.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-4 text-center text-gray-500">
                    Nog geen spelers. Voeg er een toe of importeer het sjabloon.
                  </td>
                </tr>
              )}
              {players.map((p) => (
                <Fragment key={p.id}>
                  <tr className="border-t border-gray-700">
                    <td className="px-4 py-2">{p.jersey_number ?? "—"}</td>
                    <td className="px-4 py-2">
                      {p.first_name} {p.last_name}
                    </td>
                    <td className="px-4 py-2">{p.email ?? "—"}</td>
                    <td className="px-4 py-2">{p.phone_number ?? "—"}</td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() => (testPlayerId === p.id ? setTestPlayerId(null) : openTestForm(p.id))}
                        className="text-emerald-400 hover:text-emerald-300 text-xs"
                      >
                        {testPlayerId === p.id ? "Sluiten" : "MAS-test invoeren"}
                      </button>
                    </td>
                  </tr>
                  {testPlayerId === p.id && (
                    <tr className="border-t border-gray-700 bg-gray-900/50">
                      <td colSpan={5} className="px-4 py-3">
                        <form onSubmit={handleRecordMasTest} className="flex flex-wrap items-end gap-3 text-sm">
                          <label className="flex flex-col text-gray-300">
                            Protocol
                            <select
                              value={testProtocolKey}
                              onChange={(e) => setTestProtocolKey(e.target.value)}
                              className="mt-1 bg-gray-900 text-white rounded-md px-3 py-2"
                            >
                              {protocols.map((protocol) => (
                                <option key={protocol.key} value={protocol.key}>
                                  {protocol.name}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="flex flex-col text-gray-300">
                            Resultaat (km/u)
                            <input
                              type="number"
                              step="0.1"
                              min="0.1"
                              required
                              value={testRawResult}
                              onChange={(e) => setTestRawResult(e.target.value)}
                              className="mt-1 bg-gray-900 text-white rounded-md px-3 py-2 w-28"
                            />
                          </label>
                          <label className="flex flex-col text-gray-300">
                            Testdatum
                            <input
                              type="date"
                              required
                              value={testDate}
                              onChange={(e) => setTestDate(e.target.value)}
                              className="mt-1 bg-gray-900 text-white rounded-md px-3 py-2"
                            />
                          </label>
                          <button
                            type="submit"
                            disabled={testSubmitting}
                            className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-md"
                          >
                            {testSubmitting ? "Bezig…" : "Opslaan"}
                          </button>
                          {testError && <p className="text-red-400 w-full">{testError}</p>}
                          {testConfirmation && <p className="text-emerald-400 w-full">{testConfirmation}</p>}
                        </form>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
