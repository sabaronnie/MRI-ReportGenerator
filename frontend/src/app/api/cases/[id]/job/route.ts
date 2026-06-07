import { NextResponse } from "next/server";
import { getJob } from "@/lib/api/client";

/** Job-status endpoint the client polls while a case is processing. */
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  try {
    return NextResponse.json(await getJob(id));
  } catch {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
}
