const BASE = process.env.PARLEY_API_URL ?? "http://127.0.0.1:8000";
const KEY = process.env.PARLEY_API_KEY ?? "";
const ALLOWED = new Set(["tickets", "approvals", "stats", "health"]);

export const dynamic = "force-dynamic";

type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: Request, context: Context): Promise<Response> {
  const { path } = await context.params;
  if (!path.length || !ALLOWED.has(path[0])) {
    return Response.json({ code: "forbidden", detail: "path not exposed" }, { status: 403 });
  }
  const search = new URL(request.url).search;
  const target = `${BASE}/${path.map(encodeURIComponent).join("/")}${search}`;
  const headers = new Headers({ "content-type": "application/json" });
  if (KEY) headers.set("x-api-key", KEY);
  const lastEvent = request.headers.get("last-event-id");
  if (lastEvent) headers.set("last-event-id", lastEvent);
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : await request.text(),
      cache: "no-store",
      signal: request.signal,
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") ?? "application/json",
        "cache-control": "no-cache, no-transform",
      },
    });
  } catch {
    return Response.json({ code: "upstream_unreachable", detail: "service is down" }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
