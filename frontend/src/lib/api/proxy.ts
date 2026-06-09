import { getToken } from "@/lib/auth/session";

const EEP_URL = process.env.NEXT_PUBLIC_EEP_URL ?? "";

/**
 * Stream an EEP response back to the browser with the session JWT attached.
 * Used by the /api/cases/[id]/{volume,mask,report} route handlers so the
 * NiiVue viewer and the report tab work against the now-guarded EEP without
 * ever exposing the httpOnly token to client JS.
 */
export async function proxyToEep(path: string): Promise<Response> {
  const token = await getToken();
  if (!token) return new Response("Unauthorized", { status: 401 });
  if (!EEP_URL) return new Response("EEP not configured", { status: 502 });

  const upstream = await fetch(`${EEP_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  const headers = new Headers();
  for (const h of ["content-type", "content-length", "content-disposition"]) {
    const v = upstream.headers.get(h);
    if (v) headers.set(h, v);
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}
