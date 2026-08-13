import { useState } from "react";
import { Link } from "react-router-dom";
import { forgotPassword } from "../api/client";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const res = await forgotPassword(email);
      setMessage(res.message);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-[75vh] flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-gray-900/60 border border-white/10 rounded-2xl p-8 space-y-5 shadow-xl shadow-black/20">
        <h1 className="text-2xl font-bold text-white tracking-tight">Wachtwoord vergeten</h1>
        <p className="text-sm text-gray-400">
          Vul je e-mailadres in. Als het bij ons bekend is, sturen we een link om je wachtwoord
          te resetten.
        </p>
        <label className="flex flex-col text-sm text-gray-300">
          E-mailadres
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 ring-brand"
          />
        </label>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        {message && <p className="text-emerald-400 text-sm">{message}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full btn-brand text-white px-4 py-2.5 rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "Bezig…" : "Verstuur resetlink"}
        </button>
        <p className="text-sm text-gray-400">
          <Link to="/login" className="text-brand hover:opacity-80 font-medium">
            Terug naar inloggen
          </Link>
        </p>
      </form>
    </div>
  );
}
