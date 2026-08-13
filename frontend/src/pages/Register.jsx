import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

const slugify = (value) =>
  value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-");

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [clubName, setClubName] = useState("");
  const [clubSlug, setClubSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [coachName, setCoachName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleClubNameChange = (value) => {
    setClubName(value);
    if (!slugTouched) setClubSlug(slugify(value));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await register({
        club_name: clubName,
        club_slug: clubSlug,
        coach_full_name: coachName,
        email,
        password,
      });
      navigate("/");
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-[75vh] flex items-center justify-center px-4 py-10">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-gray-900/60 border border-white/10 rounded-2xl p-8 space-y-5 shadow-xl shadow-black/20">
        <h1 className="text-2xl font-bold text-white tracking-tight">Registreer je club</h1>
        <p className="text-sm text-gray-400">
          Elke club krijgt een eigen whitelabel-omgeving met een eigen login voor de coach.
        </p>
        <label className="flex flex-col text-sm text-gray-300">
          Clubnaam
          <input
            type="text"
            required
            value={clubName}
            onChange={(e) => handleClubNameChange(e.target.value)}
            className="mt-1 bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 ring-brand"
          />
        </label>
        <label className="flex flex-col text-sm text-gray-300">
          Club-slug (url)
          <input
            type="text"
            required
            pattern="[a-z0-9\-]+"
            value={clubSlug}
            onChange={(e) => {
              setSlugTouched(true);
              setClubSlug(e.target.value);
            }}
            className="mt-1 bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 font-mono text-sm focus:outline-none focus:ring-2 ring-brand"
          />
        </label>
        <label className="flex flex-col text-sm text-gray-300">
          Naam coach
          <input
            type="text"
            required
            value={coachName}
            onChange={(e) => setCoachName(e.target.value)}
            className="mt-1 bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 ring-brand"
          />
        </label>
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
          Wachtwoord (min. 8 tekens)
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 ring-brand"
          />
        </label>
        {error && <p className="text-red-400 text-sm">{typeof error === "string" ? error : JSON.stringify(error)}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full btn-brand text-white px-4 py-2.5 rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "Bezig…" : "Registreren"}
        </button>
        <p className="text-sm text-gray-400">
          Al een account?{" "}
          <Link to="/login" className="text-brand hover:opacity-80 font-medium">
            Log in
          </Link>
        </p>
      </form>
    </div>
  );
}
