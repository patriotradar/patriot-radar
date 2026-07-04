import { createClient, SupabaseClient } from "@supabase/supabase-js";

export type TikTokResultRow = {
  id: string;
  niche: string;
  data: Record<string, unknown>;
  created_at: string;
};

export type RecentScanRow = {
  id: string;
  niche: string;
  created_at: string;
  video_count: number;
  insight_summary: string;
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

export async function fetchRecentScans(limit = 10): Promise<RecentScanRow[]> {
  const supabase = getSupabase();

  const { data: rows, error } = await supabase
    .from("tiktok_results")
    .select("id, niche, data, created_at")
    .order("created_at", { ascending: false })
    .limit(limit);

  if (error) {
    throw new Error(`Supabase fetch failed: ${error.message}`);
  }

  return (rows ?? []).map((row) => {
    const data = (row.data ?? {}) as Record<string, unknown>;
    const videos = Array.isArray(data.videos) ? data.videos : [];
    const insights = (
      typeof data.insights === "object" && data.insights !== null
        ? data.insights
        : {}
    ) as Record<string, unknown>;
    const summary =
      typeof insights.summary === "string" ? insights.summary : "";

    return {
      id: row.id as string,
      niche: row.niche as string,
      created_at: row.created_at as string,
      video_count: videos.length,
      insight_summary: summary,
    };
  });
}
