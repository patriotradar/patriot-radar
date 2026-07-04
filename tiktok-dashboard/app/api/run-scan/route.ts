import { NextRequest, NextResponse } from "next/server";

import { runScanPipeline } from "@/lib/pipeline";

export const maxDuration = 300;

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as { niche?: string };
    const niche = typeof body.niche === "string" ? body.niche.trim() : "";

    if (!niche) {
      return NextResponse.json(
        { success: false, error: "niche is required" },
        { status: 400 },
      );
    }

    const result = await runScanPipeline(niche);

    if (!result.success) {
      return NextResponse.json(result, { status: 422 });
    }

    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[run-scan]", message);
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}
