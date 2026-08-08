import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
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
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-gray-800 rounded-lg p-6 space-y-4">
        <h1 className="text-xl font-bold text-white">Inloggen</h1>
        <label className="flex flex-col text-sm text-gray-300">
          E-mailadres
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 bg-gray-900 text-white rounded-md px-3 py-2"
          />
        </label>
        <label className="flex flex-col text-sm text-gray-300">
          Wachtwoord
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 bg-gray-900 text-white rounded-md px-3 py-2"
          />
        </label>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-md"
        >
          {submitting ? "Bezig…" : "Inloggen"}
        </button>
        <p className="text-sm text-gray-400">
          Nog geen club?{" "}
          <Link to="/register" className="text-emerald-400 hover:underline">
            Registreer je club
          </Link>
        </p>
      </form>
    </div>
  );
}
