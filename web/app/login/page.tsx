"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    const supabase = createClient();
    const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });

    if (signInError) {
      setError(signInError.message);
      setSubmitting(false);
      return;
    }

    router.push("/chat");
    router.refresh();
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-5 rounded-2xl border border-white/10 bg-gray-900/60 p-8 shadow-xl shadow-black/20"
      >
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">The TopsportSpace</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-white">War room-toegang</h1>
        </div>
        <label className="flex flex-col text-sm text-gray-300">
          E-mailadres
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-1 rounded-lg border border-white/10 bg-gray-950 px-3 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </label>
        <label className="flex flex-col text-sm text-gray-300">
          Wachtwoord
          <input
            type="password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 rounded-lg border border-white/10 bg-gray-950 px-3 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </label>
        {error && <p className="text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Bezig…" : "Inloggen"}
        </button>
        <p className="text-center text-xs text-gray-500">
          Nog geen account? Vraag een uitnodiging aan de hoofdcoach.
        </p>
      </form>
    </div>
  );
}
