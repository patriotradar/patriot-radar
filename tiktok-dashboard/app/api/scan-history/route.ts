import { NextResponse } from "next/server";

import { fetchRecentScans } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const scans = await fetchRecentScans(10);
    return NextResponse.json({ scans });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[scan-history]", message);
    return NextResponse.json({ scans: [], error: message }, { status: 500 });
  }
}
