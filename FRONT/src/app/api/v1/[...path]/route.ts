/**
 * Proxy del navegador al backend FastAPI: /api/v1/* → BACKEND_URL/api/v1/*
 *
 * Reemplaza a rewrites() de next.config.ts para controlar el caso "backend apagado":
 * responde 503 {detail} con la cabecera x-backend-down y escribe UNA línea en la
 * terminal (como mucho una por minuto) en lugar de un AggregateError por petición.
 */
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");
const PASS_HEADERS = ["content-type", "content-disposition", "content-length", "cache-control", "etag", "last-modified"];

let lastLog = 0;
function logBackendDown(err: unknown) {
  const now = Date.now();
  if (now - lastLog < 60_000) return;
  lastLog = now;
  const e = err as { name?: string; cause?: { code?: string } };
  const reason = e?.cause?.code ?? e?.name ?? "error";
  console.warn(
    `[api] Backend FastAPI no disponible en ${BACKEND_URL} (${reason}). ` +
      `El front muestra datos de demostración. Levanta el backend o usa "npm run dev:mock".`,
  );
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const target = `${BACKEND_URL}/api/v1/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  try {
    const res = await fetch(target, {
      headers: { accept: req.headers.get("accept") ?? "application/json" },
      cache: "no-store",
      // Las respuestas redactadas por IA (alertas, insights, preguntas) tardan más la primera vez
      signal: AbortSignal.timeout(/^(alerts|ask)$|\/(insights|ask)$/.test(path.join("/")) || path[0] === "alerts" ? 120_000 : 15_000),
    });
    const headers = new Headers();
    for (const h of PASS_HEADERS) {
      const v = res.headers.get(h);
      if (v) headers.set(h, v);
    }
    return new Response(res.body, { status: res.status, headers });
  } catch (err) {
    logBackendDown(err);
    return Response.json(
      { detail: `Backend no disponible en ${BACKEND_URL}` },
      { status: 503, headers: { "x-backend-down": "1", "cache-control": "no-store" } },
    );
  }
}
