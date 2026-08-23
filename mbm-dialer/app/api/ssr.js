// Vercel Node serverless function bridging to the TanStack Start SSR handler
// (dist/server/server.js exports a Workers-style { fetch } — see wrangler.jsonc).
// Static files (dist/client, incl. /leads_database.json) are served by Vercel's
// static layer; every non-static path falls through here via the vercel.json
// catch-all rewrite.
export const config = {
  runtime: "nodejs",
  maxDuration: 15,
};

let handlerPromise;

async function getServer() {
  if (!handlerPromise) {
    handlerPromise = import("../dist/server/server.js");
  }
  return handlerPromise;
}

function readBody(req) {
  if (req.method === "GET" || req.method === "HEAD") return Promise.resolve(undefined);
  return new Promise((resolve) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const buf = Buffer.concat(chunks);
      resolve(buf.length > 0 ? buf : undefined);
    });
    req.on("error", () => resolve(undefined));
  });
}

export default async function handler(req, res) {
  try {
    const mod = await getServer();
    const proto = String(req.headers["x-forwarded-proto"] || "https");
    const host = String(req.headers["x-forwarded-host"] || req.headers.host || "localhost");
    const url = `${proto}://${host}${req.url || "/"}`;

    const headers = new Headers();
    for (const [k, v] of Object.entries(req.headers)) {
      if (v == null) continue;
      if (k === "content-length" || k === "transfer-encoding" || k === "connection" || k === "host") continue;
      headers.set(k, Array.isArray(v) ? v.join(", ") : String(v));
    }

    const body = await readBody(req);
    const request = new Request(url, {
      method: req.method || "GET",
      headers,
      body,
      redirect: "manual",
    });

    const response = await mod.default.fetch(request, {}, undefined);

    res.statusCode = response.status;
    response.headers.forEach((value, key) => {
      if (key === "content-encoding" || key === "transfer-encoding") return;
      res.setHeader(key, value);
    });
    const buf = Buffer.from(await response.arrayBuffer());
    res.setHeader("content-length", buf.length);
    res.end(buf);
  } catch (err) {
    console.error("[ssr] handler error:", err);
    res.statusCode = 500;
    res.setHeader("content-type", "text/plain; charset=utf-8");
    res.end("SSR error");
  }
}
