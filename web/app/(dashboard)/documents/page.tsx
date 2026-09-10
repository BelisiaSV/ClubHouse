import { createClient } from "@/lib/supabase/server";

export default async function DocumentsPage() {
  const supabase = await createClient();
  const { data: documents } = await supabase
    .from("documents")
    .select("id, title, file_type, tags, created_at")
    .order("created_at", { ascending: false });

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Documenten &amp; Content</h1>
        <p className="mt-1 text-2xl font-bold text-white">Documentenoverzicht</p>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3 font-medium">Titel</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Tags</th>
              <th className="px-4 py-3 font-medium">Toegevoegd</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {(documents ?? []).map((document) => (
              <tr key={document.id}>
                <td className="px-4 py-3 text-gray-100">{document.title}</td>
                <td className="px-4 py-3 text-gray-400 uppercase">{document.file_type}</td>
                <td className="px-4 py-3 text-gray-400">{document.tags.join(", ") || "—"}</td>
                <td className="px-4 py-3 text-gray-400">{new Date(document.created_at).toLocaleDateString("nl-BE")}</td>
              </tr>
            ))}
            {(documents ?? []).length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-sm text-gray-500">
                  Nog geen documenten geüpload. Upload + zoeken volgt als volgende stap.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
