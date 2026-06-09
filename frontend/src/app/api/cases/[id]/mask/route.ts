import { proxyToEep } from "@/lib/api/proxy";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const type = new URL(req.url).searchParams.get("type") ?? "tss";
  return proxyToEep(`/cases/${encodeURIComponent(id)}/mask?type=${encodeURIComponent(type)}`);
}
