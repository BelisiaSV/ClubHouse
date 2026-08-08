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
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4 py-10">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-gray-800 rounded-lg p-6 space-y-4">
        <h1 className="text-xl font-bold text-white">Registreer je club</h1>
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
            className="mt-1 bg-gray-900 text-white rounded-md px-3 py-2"
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
            className="mt-1 bg-gray-900 text-white rounded-md px-3 py-2 font-mono text-sm"
          />
        </label>
        <label className="flex flex-col text-sm text-gray-300">
          Naam coach
          <input
            type="text"
            required
            value={coachName}
            onChange={(e) => setCoachName(e.target.value)}
            className="mt-1 bg-gray-900 text-white rounded-md px-3 py-2"
          />
        </label>
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
          Wachtwoord (min. 8 tekens)
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 bg-gray-900 text-white rounded-md px-3 py-2"
          />
        </label>
        {error && <p className="text-red-400 text-sm">{typeof error === "string" ? error : JSON.stringify(error)}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-md"
        >
          {submitting ? "Bezig…" : "Registreren"}
        </button>
        <p className="text-sm text-gray-400">
          Al een account?{" "}
          <Link to="/login" className="text-emerald-400 hover:underline">
            Log in
          </Link>
        </p>
      </form>
    </div>
  );
}
