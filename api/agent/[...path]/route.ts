// app/api/agent/[...path]/route.ts

import { NextRequest } from "next/server";

const BACKEND_BASE_URL =
  process.env.BACKEND_URL || "http://localhost:8000";

async function proxyRequest(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<Response> {

  // ✅ Next.js 16 requires awaiting params
  const { path } = await context.params;

  const subPath = path?.join("/") ?? "";
  const targetUrl = `${BACKEND_BASE_URL}/api/agent/${subPath}`;

  const contentType = request.headers.get("content-type") || "";
  const isMultipart = contentType.includes("multipart/form-data");

  let body: BodyInit | null = null;

  if (request.method !== "GET") {
    if (isMultipart) {
      body = await request.formData();
    } else {
      body = await request.text();
    }
  }

  const response = await fetch(targetUrl, {
    method: request.method,
    headers: {
      ...(isMultipart ? {} : { "Content-Type": "application/json" }),
    },
    body,
  });

  const responseText = await response.text();

  return new Response(responseText, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get("content-type") || "application/json",
    },
  });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}