import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import DugoutChat from "@/components/dugout-chat/DugoutChat";

export default async function ChatPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const [{ data: profiles }, { data: messages }] = await Promise.all([
    supabase.from("profiles").select("id, full_name, avatar_url, role").order("full_name"),
    supabase.from("messages").select("*").order("created_at", { ascending: true }).limit(100),
  ]);

  return (
    <main className="mx-auto flex h-[calc(100vh-2rem)] max-w-3xl flex-col px-4 py-4">
      <DugoutChat currentUserId={user.id} profiles={profiles ?? []} initialMessages={messages ?? []} />
    </main>
  );
}
