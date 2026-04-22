/**
 * web/app/api/export-report/route.ts
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import { cookies } from "next/headers";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  const headers: Record<string, string> = {};
  
  const explicit = req.headers.get("authorization");
  if (explicit) {
    headers["Authorization"] = explicit;
  } else {
    const cookieStore = cookies();
    const cookieToken = cookieStore.get("medos_token")?.value;
    if (cookieToken) headers["Authorization"] = `Bearer ${cookieToken}`;
  }

  const res = await fetch(`${BACKEND}/api/export-report`, { headers });
  
  if (!res.ok) {
    return new Response(await res.text(), { status: res.status });
  }

  // Stream the PDF directly back
  const disposition = res.headers.get("content-disposition");
  const responseHeaders = new Headers();
  responseHeaders.set("Content-Type", "application/pdf");
  if (disposition) responseHeaders.set("Content-Disposition", disposition);

  return new Response(res.body, {
    status: 200,
    headers: responseHeaders,
  });
}
