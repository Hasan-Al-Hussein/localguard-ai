import { NextResponse, type NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const KIB = 1024;
const MIB = 1024 * KIB;

type Method = "GET" | "HEAD" | "POST" | "PATCH" | "DELETE";

type RoutePolicy = {
  pattern: RegExp;
  methods: Partial<Record<Method, number>>;
};

// Limits cover the complete encoded request. Uploads retain bounded room for
// multipart headers around the API's maximum 10 MiB file.
const ROUTE_POLICIES: readonly RoutePolicy[] = [
  { pattern: /^health\/(?:live|ready)$/, methods: { GET: 0, HEAD: 0 } },
  { pattern: /^auth\/login$/, methods: { POST: 4 * KIB } },
  { pattern: /^auth\/(?:me|csrf)$/, methods: { GET: 0, HEAD: 0 } },
  { pattern: /^auth\/logout$/, methods: { POST: 0 } },
  { pattern: /^overview$/, methods: { GET: 0, HEAD: 0 } },
  { pattern: /^documents$/, methods: { GET: 0, HEAD: 0, POST: 11 * MIB } },
  { pattern: /^documents\/[^/]+$/, methods: { GET: 0, HEAD: 0, DELETE: 0 } },
  { pattern: /^documents\/[^/]+\/pages\/[^/]+$/, methods: { GET: 0, HEAD: 0 } },
  {
    pattern: /^documents\/[^/]+\/revisions\/[^/]+\/anchors\/[^/]+$/,
    methods: { GET: 0, HEAD: 0 },
  },
  { pattern: /^documents\/[^/]+\/reprocess$/, methods: { POST: 0 } },
  { pattern: /^questions$/, methods: { GET: 0, HEAD: 0, POST: 32 * KIB } },
  { pattern: /^questions\/[^/]+$/, methods: { GET: 0, HEAD: 0 } },
  { pattern: /^workflow-runs$/, methods: { POST: 32 * KIB } },
  { pattern: /^workflow-runs\/[^/]+$/, methods: { GET: 0, HEAD: 0 } },
  { pattern: /^findings$/, methods: { GET: 0, HEAD: 0 } },
  { pattern: /^approvals$/, methods: { GET: 0, HEAD: 0 } },
  { pattern: /^approvals\/[^/]+$/, methods: { GET: 0, HEAD: 0 } },
  {
    pattern: /^approvals\/[^/]+\/(?:approve|reject|edit)$/,
    methods: { POST: 16 * KIB },
  },
  { pattern: /^tasks$/, methods: { GET: 0, HEAD: 0 } },
  { pattern: /^tasks\/[^/]+$/, methods: { GET: 0, HEAD: 0, PATCH: 8 * KIB } },
  { pattern: /^audit-events$/, methods: { GET: 0, HEAD: 0 } },
  { pattern: /^audit-events\/[^/]+$/, methods: { GET: 0, HEAD: 0 } },
  { pattern: /^evaluations$/, methods: { GET: 0, HEAD: 0 } },
  { pattern: /^evaluations\/(?:latest|[^/]+)$/, methods: { GET: 0, HEAD: 0 } },
] as const;

const REQUEST_HEADER_ALLOWLIST = [
  "accept",
  "content-type",
  "cookie",
  "idempotency-key",
  "x-correlation-id",
  "x-csrf-token",
] as const;

const RESPONSE_HEADER_ALLOWLIST = [
  "cache-control",
  "content-disposition",
  "content-type",
  "retry-after",
  "x-correlation-id",
  "x-csrf-token",
] as const;

class ProxyInputError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly allow?: string,
  ) {
    super(message);
  }
}

function getApiBaseUrl(): URL {
  const configured = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  const url = new URL(configured);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("API_INTERNAL_URL must use http or https");
  }
  return url;
}

function copyAllowedRequestHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  for (const name of REQUEST_HEADER_ALLOWLIST) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  return headers;
}

function copyAllowedResponseHeaders(source: Headers): Headers {
  const headers = new Headers();
  for (const name of RESPONSE_HEADER_ALLOWLIST) {
    const value = source.get(name);
    if (value) headers.set(name, value);
  }

  const cookieHeaders = source.getSetCookie?.() ?? [];
  for (const cookie of cookieHeaders) headers.append("set-cookie", cookie);
  headers.set("cache-control", "private, no-store");
  return headers;
}

function errorResponse(
  status: number,
  code: string,
  message: string,
  correlationId: string,
  extraHeaders?: HeadersInit,
) {
  const headers = new Headers(extraHeaders);
  headers.set("cache-control", "private, no-store");
  return NextResponse.json(
    { error: { code, message, correlation_id: correlationId } },
    { status, headers },
  );
}

function resolvePolicy(pathname: string, method: string): { maxBodyBytes: number } {
  const policy = ROUTE_POLICIES.find((candidate) => candidate.pattern.test(pathname));
  if (!policy) {
    throw new ProxyInputError(404, "route_not_allowed", "The requested API route is not available.");
  }

  if (!(method in policy.methods)) {
    const allow = Object.keys(policy.methods).join(", ");
    throw new ProxyInputError(405, "method_not_allowed", `This API route allows: ${allow}.`, allow);
  }

  return { maxBodyBytes: policy.methods[method as Method] ?? 0 };
}

function declaredContentLength(request: NextRequest): number | null {
  const raw = request.headers.get("content-length");
  if (raw == null) return null;
  if (!/^\d+$/.test(raw)) {
    throw new ProxyInputError(400, "invalid_content_length", "Content-Length must be a non-negative integer.");
  }
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed)) {
    throw new ProxyInputError(400, "invalid_content_length", "Content-Length is outside the supported range.");
  }
  return parsed;
}

async function readBoundedBody(request: NextRequest, maxBodyBytes: number): Promise<ArrayBuffer | undefined> {
  const declared = declaredContentLength(request);
  if (declared != null && declared > maxBodyBytes) {
    throw new ProxyInputError(413, "request_too_large", "The request body exceeds this route's size limit.");
  }

  if (!request.body) {
    if ((declared ?? 0) > 0) {
      throw new ProxyInputError(400, "invalid_request_body", "The declared request body was not available.");
    }
    return undefined;
  }

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      received += value.byteLength;
      if (received > maxBodyBytes) {
        await reader.cancel("request body too large");
        throw new ProxyInputError(413, "request_too_large", "The request body exceeds this route's size limit.");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  if (declared != null && declared !== received) {
    throw new ProxyInputError(400, "invalid_content_length", "Content-Length did not match the received body.");
  }
  if (received === 0) return undefined;

  const body = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body.buffer as ArrayBuffer;
}

async function forward(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const correlationId = request.headers.get("x-correlation-id") ?? crypto.randomUUID();

  try {
    const { path } = await context.params;
    if (!path.length || path.some((segment) => segment.length === 0 || segment.length > 160)) {
      throw new ProxyInputError(404, "route_not_allowed", "The requested API route is not available.");
    }

    const pathname = path.join("/");
    const method = request.method.toUpperCase();
    const { maxBodyBytes } = resolvePolicy(pathname, method);
    const body = method === "GET" || method === "HEAD" ? undefined : await readBoundedBody(request, maxBodyBytes);
    const target = new URL(path.map(encodeURIComponent).join("/"), `${getApiBaseUrl().toString().replace(/\/$/, "")}/`);
    target.search = request.nextUrl.search;

    const headers = copyAllowedRequestHeaders(request);
    headers.set("x-correlation-id", correlationId);

    const upstream = await fetch(target, {
      method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(180_000),
    });

    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: copyAllowedResponseHeaders(upstream.headers),
    });
  } catch (error) {
    if (error instanceof ProxyInputError) {
      return errorResponse(
        error.status,
        error.code,
        error.message,
        correlationId,
        error.allow ? { Allow: error.allow } : undefined,
      );
    }
    return errorResponse(
      503,
      "api_unavailable",
      "LocalGuard services are unavailable. Start the local stack, then try again.",
      correlationId,
    );
  }
}

export const GET = forward;
export const HEAD = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
