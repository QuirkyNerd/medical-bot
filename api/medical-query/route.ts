/**
 * /api/medical-query/route.ts
 * ============================
 * Unified Medical Query API — Next.js App Router handler.
 *
 * Routing logic:
 *   All types ("text", "image", "pdf") → Python FastAPI backend
 */

export const maxDuration = 90;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MedicalQueryRequest {
  type: "text" | "image" | "pdf";
  query?: string;
  top_k?: number;
  rag_filters?: Record<string, unknown>;
  image?: string;
  pdf?: string;
  message?: string;
}

interface UnifiedResponse {
  type: "text" | "image" | "pdf";
  answer: string;
  confidence?: number;
  sources?: string[];
  model_used?: string;
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// POST handler
// ---------------------------------------------------------------------------

export async function POST(req: Request): Promise<Response> {
  let body: MedicalQueryRequest;

  try {
    body = await req.json();
  } catch {
    return Response.json(
      { success: false, error: "Invalid JSON body" },
      { status: 400 }
    );
  }

  const { type } = body;

  if (!type || !["text", "image", "pdf"].includes(type)) {
    return Response.json(
      {
        success: false,
        error: `Invalid or missing 'type'. Expected "text", "image", or "pdf". Got: ${JSON.stringify(type)}`,
      },
      { status: 400 }
    );
  }

  console.log(`🏥 [medical-query] type=${type}`);

  try {
    // Forward directly to the FastAPI backend
    const backendRes = await fetch(`${BACKEND_URL}/api/medical-query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(85_000),
    });

    if (!backendRes.ok) {
      const errorText = await backendRes.text();
      console.error(
        `❌ [medical-query/${type}] Backend returned ${backendRes.status}: ${errorText}`
      );
      return Response.json(
        {
          success: false,
          error: `Backend error (${backendRes.status}): ${errorText}`,
        },
        { status: backendRes.status }
      );
    }

    const data: UnifiedResponse = await backendRes.json();
    return Response.json({ success: true, ...data });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`💥 [medical-query] Unhandled error (type=${type}):`, message);
    return Response.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
