import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "@/app/api/[...path]/route";

function context(...path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("same-origin API proxy", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("rejects an oversized declared body before contacting the API", async () => {
    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      headers: { "content-length": "4097", "content-type": "application/json" },
      body: "{}",
    });

    const response = await POST(request, context("auth", "login"));
    expect(response.status).toBe(413);
    await expect(response.json()).resolves.toMatchObject({ error: { code: "request_too_large" } });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("counts a chunked body and rejects it once the route limit is crossed", async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new Uint8Array(4097));
        controller.close();
      },
    });
    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: stream,
      duplex: "half",
    } as never);

    const response = await POST(request, context("auth", "login"));
    expect(response.status).toBe(413);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("forwards only allowlisted mutation metadata including Idempotency-Key", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ accepted: true }), {
      status: 202,
      headers: { "content-type": "application/json" },
    }));
    const request = new NextRequest("http://localhost/api/questions", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "idempotency-key": "question-12345678",
        "x-not-allowed": "secret",
      },
      body: JSON.stringify({ question: "What is required?", document_ids: [] }),
    });

    const response = await POST(request, context("questions"));
    expect(response.status).toBe(202);
    const init = vi.mocked(fetch).mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);
    expect(headers.get("idempotency-key")).toBe("question-12345678");
    expect(headers.has("x-not-allowed")).toBe(false);
  });
});
