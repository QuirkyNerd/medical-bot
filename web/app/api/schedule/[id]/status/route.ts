/**
 * web/app/api/schedule/[id]/status/route.ts
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import { cookies } from "next/headers";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  
  const explicit = req.headers.get("authorization");
  if (explicit) {
    headers["Authorization"] = explicit;
  } else {
    const cookieStore = cookies();
    const cookieToken = cookieStore.get("medos_token")?.value;
    if (cookieToken) headers["Authorization"] = `Bearer ${cookieToken}`;
  }

  const body = await req.text();
  const init: RequestInit = { method: "PATCH", headers, body };
  const res = await fetch(`${BACKEND}/api/schedule/${params.id}/status`, init);
  
  const data = await res.text();
  return new Response(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
