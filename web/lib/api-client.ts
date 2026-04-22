/**
 * Shared API client for frontend-backend communication.
 * Replaces direct fetch calls and handles environment-specific URLs,
 * token injection, and error normalization.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export interface ApiOptions extends RequestInit {
  token?: string | null;
  json?: any;
}

export async function apiRequest<T = any>(
  path: string,
  options: ApiOptions = {}
): Promise<T> {
  const { token, json, headers: customHeaders, ...rest } = options;

  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;

  const headers = new Headers(customHeaders);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (json && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const config: RequestInit = {
    ...rest,
    headers,
  };

  if (json) {
    config.body = JSON.stringify(json);
  } else if (rest.body instanceof FormData) {
    // Note: Do NOT set Content-Type for FormData, the browser will do it with the boundary
    config.body = rest.body;
  }

  try {
    const response = await fetch(url, config);
    
    // Attempt to parse JSON even if response is not OK to get error details
    let data: any;
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      data = await response.json();
    } else {
      data = { error: await response.text() };
    }

    if (!response.ok) {
      const error = data?.error || data?.detail || `API error: ${response.status}`;
      throw new Error(error);
    }

    return data as T;
  } catch (error: any) {
    console.error(`API Request failed: ${url}`, error);
    throw error;
  }
}
