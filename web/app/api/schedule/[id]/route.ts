/**
 * web/app/api/schedule/[id]/route.ts
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import { cookies } from "next/headers";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxy(req: Request, id: string) {
  const headers: Record<string, string> = {};
  
  const explicit = req.headers.get("authorization");
  if (explicit) {
    headers["Authorization"] = explicit;
  } else {
    const cookieStore = cookies();
    const cookieToken = cookieStore.get("medos_token")?.value;
    if (cookieToken) headers["Authorization"] = `Bearer ${cookieToken}`;
  }

  const init: RequestInit = { method: req.method, headers };
  const res = await fetch(`${BACKEND}/api/schedule/${id}`, init);
  const data = await res.text();
  return new Response(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function DELETE(req: Request, { params }: { params: { id: string } }) {
  return proxy(req, params.id);
}
