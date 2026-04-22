/**
 * web/app/api/schedule/route.ts
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import { cookies } from "next/headers";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxy(req: Request) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  
  const explicit = req.headers.get("authorization");
  if (explicit) {
    headers["Authorization"] = explicit;
  } else {
    const cookieStore = cookies();
    const cookieToken = cookieStore.get("medos_token")?.value;
    if (cookieToken) headers["Authorization"] = `Bearer ${cookieToken}`;
  }

  const init: RequestInit = { method: req.method, headers };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  const res = await fetch(`${BACKEND}/api/schedule`, init);
  const data = await res.text();
  return new Response(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function GET(req: Request) { return proxy(req); }
export async function POST(req: Request) { return proxy(req); }
