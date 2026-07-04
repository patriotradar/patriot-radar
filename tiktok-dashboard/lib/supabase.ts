import { createClient, SupabaseClient } from "@supabase/supabase-js";

export type TikTokResultRow = {
  id: string;
  niche: string;
  data: Record<string, unknown>;
  created_at: string;
};

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (client) {
    return client;
  }

  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_KEY;

  if (!url || !key) {
    throw new Error("SUPABASE_URL and SUPABASE_KEY must be configured");
  }

  client = createClient(url, key);
  return client;
}

export async function storeTikTokResults(
  niche: string,
  data: Record<string, unknown>,
): Promise<TikTokResultRow> {
  const supabase = getSupabase();

  const { data: row, error } = await supabase
    .from("tiktok_results")
    .insert({ niche, data })
    .select("id, niche, data, created_at")
    .single();

  if (error) {
    throw new Error(`Supabase insert failed: ${error.message}`);
  }

  return row as TikTokResultRow;
}
