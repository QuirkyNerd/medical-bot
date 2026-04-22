/**
 * web/app/api/conversations/route.ts
 * Proxy: /api/conversations → backend /api/conversations
 * Forwards both cookie token AND explicit Authorization header.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import { cookies } from "next/headers";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxy(req: Request, path: string) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  // 1. Prefer explicit Authorization header (set by useChat fetch calls)
  const explicit = req.headers.get("authorization");
  if (explicit) {
    headers["Authorization"] = explicit;
  } else {
    // 2. Fall back to httpOnly cookie (set by useAuth on login)
    const cookieStore = cookies();
    const cookieToken = cookieStore.get("medos_token")?.value;
    if (cookieToken) headers["Authorization"] = `Bearer ${cookieToken}`;
  }

  const init: RequestInit = { method: req.method, headers };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  const res = await fetch(`${BACKEND}${path}`, init);
  const data = await res.text();
  return new Response(data, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function GET(req: Request) {
  return proxy(req, "/api/conversations");
}

export async function POST(req: Request) {
  return proxy(req, "/api/conversations");
}
