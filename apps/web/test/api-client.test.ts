import { z } from "zod";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest, setCsrfToken } from "@/lib/api-client";

const ResultSchema = z.object({ ok: z.boolean() });

describe("apiRequest", () => {
  beforeEach(() => {
    setCsrfToken(null);
    vi.stubGlobal("fetch", vi.fn());
  });

  it("loads an in-memory CSRF token before a state-changing request", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "csrf-token-at-least-16" }), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));

    await expect(apiRequest("/documents/doc-1/reprocess", ResultSchema, { method: "POST", body: "{}" })).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/auth/csrf");
    const mutation = fetchMock.mock.calls[1];
    expect(mutation?.[0]).toBe("/api/documents/doc-1/reprocess");
    expect(mutation?.[1]).toMatchObject({ method: "POST", credentials: "same-origin", cache: "no-store" });
    expect(new Headers(mutation?.[1]?.headers).get("x-csrf-token")).toBe("csrf-token-at-least-16");
  });

  it("does not request CSRF for reads", async () => {
    const fetchMock = vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));

    await apiRequest("/overview", ResultSchema);

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/overview");
  });

  it("returns a sanitized typed API error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({
      error: { code: "forbidden", message: "Reviewer role required", correlation_id: "corr-1" },
    }), { status: 403, headers: { "content-type": "application/json" } }));

    const result = apiRequest("/audit", ResultSchema);
    await expect(result).rejects.toMatchObject({ status: 403, code: "forbidden", correlationId: "corr-1" } satisfies Partial<ApiError>);
  });

  it("turns malformed successful payloads into a safe typed error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response("not-json and never exposed", {
      status: 200,
      headers: { "content-type": "application/json", "x-correlation-id": "corr-invalid" },
    }));

    const result = apiRequest("/overview", ResultSchema);
    await expect(result).rejects.toMatchObject({
      message: "The local API returned an invalid response.",
      status: 200,
      code: "invalid_response",
      correlationId: "corr-invalid",
    } satisfies Partial<ApiError>);
    await expect(result).rejects.not.toThrow("not-json");
  });

  it("rejects paths that could leave the same-origin API boundary", async () => {
    await expect(apiRequest("https://example.com/private", ResultSchema)).rejects.toThrow("same-origin");
    expect(fetch).not.toHaveBeenCalled();
  });
});
