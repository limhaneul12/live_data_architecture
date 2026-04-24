import { NextRequest } from "next/server";

const BACKEND_API_BASE_URL = (process.env.BACKEND_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

export async function GET(_request: NextRequest, context: RouteContext): Promise<Response> {
  const url = await analyticsUrl(context);
  return proxyRequest(url, { method: "GET" });
}

export async function POST(request: NextRequest, context: RouteContext): Promise<Response> {
  const url = await analyticsUrl(context);
  const body = await request.text();
  return proxyRequest(url, {
    method: "POST",
    headers: { "content-type": request.headers.get("content-type") ?? "application/json" },
    body,
  });
}

async function analyticsUrl(context: RouteContext): Promise<string> {
  const { path } = await context.params;
  return `${BACKEND_API_BASE_URL}/analytics/${path.map(encodeURIComponent).join("/")}`;
}

async function proxyRequest(url: string, init: RequestInit): Promise<Response> {
  try {
    const response = await fetch(url, {
      ...init,
      cache: "no-store",
    });
    const contentType = response.headers.get("content-type") ?? "application/json";
    return new Response(await response.text(), {
      status: response.status,
      headers: { "content-type": contentType },
    });
  } catch (error) {
    return Response.json(
      {
        error_code: "backend_unavailable",
        message: "analytics backend에 연결할 수 없습니다.",
        rejected_reason: error instanceof Error ? error.message : "unknown backend connection error",
      },
      { status: 503 },
    );
  }
}
