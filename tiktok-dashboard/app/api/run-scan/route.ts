import { NextRequest, NextResponse } from "next/server";

import { runScanPipeline, type ProgressEvent } from "@/lib/pipeline";

export const maxDuration = 300;

function sseChunk(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export async function POST(request: NextRequest) {
  const acceptsStream = request.headers.get("accept")?.includes("text/event-stream") ?? false;

  let body: { niche?: string };
  try {
    body = (await request.json()) as { niche?: string };
  } catch {
    const errPayload = { success: false, step: "invalid_input", error: "Invalid JSON body" };
    if (acceptsStream) {
      return new Response(sseChunk("error", errPayload), {
        status: 400,
        headers: { "Content-Type": "text/event-stream" },
      });
    }
    return NextResponse.json(errPayload, { status: 400 });
  }

  const niche = typeof body.niche === "string" ? body.niche.trim() : "";

  if (!niche) {
    const errPayload = { success: false, step: "invalid_input", error: "niche is required" };
    if (acceptsStream) {
      return new Response(sseChunk("error", errPayload), {
        status: 400,
        headers: { "Content-Type": "text/event-stream" },
      });
    }
    return NextResponse.json(errPayload, { status: 400 });
  }

  // Streaming path
  if (acceptsStream) {
    const { readable, writable } = new TransformStream<Uint8Array, Uint8Array>();
    const writer = writable.getWriter();
    const encoder = new TextEncoder();

    const write = async (chunk: string) => {
      await writer.write(encoder.encode(chunk));
    };

    const onProgress = (event: ProgressEvent) => {
      void write(sseChunk("progress", event));
    };

    // Run pipeline in background, writing progress and final result to the stream.
    void (async () => {
      try {
        const result = await runScanPipeline(niche, onProgress);
        if (result.success) {
          await write(sseChunk("result", result));
        } else {
          await write(sseChunk("error", result));
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        console.error("[run-scan SSE]", message);
        await write(
          sseChunk("error", { success: false, step: "search_failed", error: message }),
        );
      } finally {
        await writer.close();
      }
    })();

    return new Response(readable as unknown as BodyInit, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }

  // Non-streaming path (unchanged behaviour)
  try {
    const result = await runScanPipeline(niche);

    if (!result.success) {
      return NextResponse.json(result, { status: 422 });
    }

    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[run-scan]", message);
    return NextResponse.json(
      { success: false, step: "search_failed", error: message },
      { status: 500 },
    );
  }
}
