import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-[75vh] flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-gray-900/60 border border-white/10 rounded-2xl p-8 space-y-5 shadow-xl shadow-black/20">
        <h1 className="text-2xl font-bold text-white tracking-tight">Inloggen</h1>
        {location.state?.resetSuccess && (
          <p className="text-emerald-400 text-sm">
            Wachtwoord succesvol gewijzigd. Log in met je nieuwe wachtwoord.
          </p>
        )}
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
        <label className="flex flex-col text-sm text-gray-300">
          Wachtwoord
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 ring-brand"
          />
        </label>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full btn-brand text-white px-4 py-2.5 rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "Bezig…" : "Inloggen"}
        </button>
        <div className="flex items-center justify-between text-sm text-gray-400">
          <Link to="/register" className="text-brand hover:opacity-80 font-medium">
            Registreer je club
          </Link>
          <Link to="/forgot-password" className="text-brand hover:opacity-80 font-medium">
            Wachtwoord vergeten?
          </Link>
        </div>
      </form>
    </div>
  );
}
