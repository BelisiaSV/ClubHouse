import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { resetPassword } from "../api/client";

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const navigate = useNavigate();

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("Wachtwoorden komen niet overeen.");
      return;
    }
    setSubmitting(true);
    try {
      await resetPassword(token, newPassword);
      navigate("/login", { state: { resetSuccess: true } });
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-[75vh] flex items-center justify-center px-4">
        <div className="w-full max-w-sm bg-gray-900/60 border border-white/10 rounded-2xl p-8 space-y-5 text-center shadow-xl shadow-black/20">
          <p className="text-red-400">Geen resettoken gevonden. Vraag een nieuwe resetlink aan.</p>
          <Link to="/forgot-password" className="text-brand hover:opacity-80 text-sm font-medium">
            Wachtwoord vergeten
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[75vh] flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-gray-900/60 border border-white/10 rounded-2xl p-8 space-y-5 shadow-xl shadow-black/20">
        <h1 className="text-2xl font-bold text-white tracking-tight">Nieuw wachtwoord instellen</h1>
        <label className="flex flex-col text-sm text-gray-300">
          Nieuw wachtwoord (min. 8 tekens)
          <input
            type="password"
            required
            minLength={8}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="mt-1 bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 ring-brand"
          />
        </label>
        <label className="flex flex-col text-sm text-gray-300">
          Bevestig nieuw wachtwoord
          <input
            type="password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-1 bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 ring-brand"
          />
        </label>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full btn-brand text-white px-4 py-2.5 rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "Bezig…" : "Wachtwoord wijzigen"}
        </button>
      </form>
    </div>
  );
}
