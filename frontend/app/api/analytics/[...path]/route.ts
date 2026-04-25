import { NextRequest } from "next/server";

const BACKEND_API_BASE_URL = (process.env.BACKEND_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const MAX_ANALYTICS_PROXY_BODY_BYTES = 16_384;

type AnalyticsProxyMethod = "GET" | "POST";
type AnalyticsProxyRoute = {
  backendPath: string;
  methods: readonly AnalyticsProxyMethod[];
};

const ANALYTICS_PROXY_ROUTES = {
  datasets: { backendPath: "datasets", methods: ["GET"] },
  "explore-query": { backendPath: "explore-query", methods: ["POST"] },
  presets: { backendPath: "presets", methods: ["GET"] },
  query: { backendPath: "query", methods: ["POST"] },
  "view-tables": { backendPath: "view-tables", methods: ["GET", "POST"] },
  "view-tables/preview": { backendPath: "view-tables/preview", methods: ["POST"] },
} as const satisfies Record<string, AnalyticsProxyRoute>;

type AnalyticsProxyRouteName = keyof typeof ANALYTICS_PROXY_ROUTES;

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

export async function GET(_request: NextRequest, context: RouteContext): Promise<Response> {
  const route = await analyticsRoute(context);
  if (route === null) {
    return unknownRouteResponse();
  }
  if (!route.methods.includes("GET")) {
    return methodNotAllowedResponse(route.methods);
  }
  return proxyRequest(analyticsUrl(route.backendPath), { method: "GET" });
}

export async function POST(request: NextRequest, context: RouteContext): Promise<Response> {
  const route = await analyticsRoute(context);
  if (route === null) {
    return unknownRouteResponse();
  }
  if (!route.methods.includes("POST")) {
    return methodNotAllowedResponse(route.methods);
  }
  if (contentLengthExceedsLimit(request)) {
    return payloadTooLargeResponse();
  }
  const body = await request.text();
  if (new TextEncoder().encode(body).length > MAX_ANALYTICS_PROXY_BODY_BYTES) {
    return payloadTooLargeResponse();
  }
  return proxyRequest(analyticsUrl(route.backendPath), {
    method: "POST",
    headers: { "content-type": request.headers.get("content-type") ?? "application/json" },
    body,
  });
}

async function analyticsRoute(context: RouteContext): Promise<AnalyticsProxyRoute | null> {
  const { path } = await context.params;
  if (path.length === 0) {
    return null;
  }
  const routeName = path.join("/");
  if (!isAnalyticsProxyRouteName(routeName)) {
    return null;
  }
  return ANALYTICS_PROXY_ROUTES[routeName];
}

function analyticsUrl(backendPath: string): string {
  const safeBackendPath = backendPath.split("/").map(encodeURIComponent).join("/");
  return `${BACKEND_API_BASE_URL}/analytics/${safeBackendPath}`;
}

function isAnalyticsProxyRouteName(routeName: string): routeName is AnalyticsProxyRouteName {
  return Object.hasOwn(ANALYTICS_PROXY_ROUTES, routeName);
}

function contentLengthExceedsLimit(request: NextRequest): boolean {
  const contentLength = request.headers.get("content-length");
  if (contentLength === null) {
    return false;
  }
  const parsedContentLength = Number(contentLength);
  return Number.isFinite(parsedContentLength) && parsedContentLength > MAX_ANALYTICS_PROXY_BODY_BYTES;
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
  } catch {
    return Response.json(
      {
        error_code: "backend_unavailable",
        message: "analytics backend에 연결할 수 없습니다.",
        rejected_reason: "backend_connection_failed",
      },
      { status: 503 },
    );
  }
}

function unknownRouteResponse(): Response {
  return Response.json(
    {
      error_code: "analytics_proxy_route_not_allowed",
      message: "허용되지 않은 analytics proxy 경로입니다.",
      rejected_reason: "unknown_analytics_proxy_route",
    },
    { status: 404 },
  );
}

function methodNotAllowedResponse(allowedMethods: readonly AnalyticsProxyMethod[]): Response {
  return Response.json(
    {
      error_code: "analytics_proxy_method_not_allowed",
      message: "허용되지 않은 analytics proxy method입니다.",
      rejected_reason: "method_not_allowed",
    },
    {
      status: 405,
      headers: { allow: allowedMethods.join(", ") },
    },
  );
}

function payloadTooLargeResponse(): Response {
  return Response.json(
    {
      error_code: "analytics_proxy_payload_too_large",
      message: "analytics proxy 요청 본문이 너무 큽니다.",
      rejected_reason: "payload_too_large",
    },
    { status: 413 },
  );
}
