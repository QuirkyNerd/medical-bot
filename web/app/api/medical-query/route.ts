/**
 * web/app/api/medical-query/route.ts
 * ====================================
 * Unified Frontend API Proxy — forwards to FastAPI backend.
 */

export const dynamic = "force-dynamic";
export const maxDuration = 90;

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

interface MedicalQueryBody {
  type: "text" | "image" | "pdf";
  query?: string;
  image?: string; 
  message?: string; 
  pdf?: string; 
}

export async function POST(req: Request): Promise<Response> {
  let body: MedicalQueryBody;

  try {
    body = await req.json();
  } catch {
    return Response.json({ success: false, error: "Invalid JSON body" }, { status: 400 });
  }

  const { type } = body;

  if (!type || !["text", "image", "pdf"].includes(type)) {
    return Response.json(
      { success: false, error: `'type' must be "text", "image", or "pdf". Received: ${JSON.stringify(type)}` },
      { status: 400 }
    );
  }

  console.log(`🏥 [medical-query proxy] type=${type} → Python backend`);

  try {
    const res = await fetch(`${BACKEND_URL}/api/medical-query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(85_000),
    });

    if (!res.ok) {
      let errText = res.statusText;
      try {
        const j = await res.json();
        errText = j.error ?? j.detail ?? res.statusText;
      } catch {}
      console.error(`❌ Backend ${res.status}: ${errText}`);
      return Response.json({ success: false, error: `Backend error (${res.status}): ${errText}` }, { status: res.status });
    }

    const data = await res.json();
    return Response.json({ success: true, ...data });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("❌ [medical-query proxy] fetch failed:", msg);

    const isNetworkErr =
      msg.includes("ECONNREFUSED") ||
      msg.includes("fetch failed") ||
      msg.includes("TimeoutError");

    return Response.json(
      { success: false, error: isNetworkErr ? "The medical backend is unreachable. Ensure the Python server is running on port 8000." : `Pipeline error: ${msg}` },
      { status: 502 }
    );
  }
}
