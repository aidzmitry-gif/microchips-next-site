import { NextResponse } from "next/server";
import { revalidatePath } from "next/cache";

type RevalidateRequest = { paths?: unknown };

export async function POST(request: Request) {
  const secret = process.env.NEXT_REVALIDATE_SECRET;
  const authorization = request.headers.get("authorization");

  if (!secret || authorization !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as RevalidateRequest;
  const paths = Array.isArray(body.paths)
    ? body.paths.filter((path): path is string => typeof path === "string" && path.startsWith("/"))
    : [];

  for (const path of paths) revalidatePath(path);

  return NextResponse.json({ revalidated: paths });
}
