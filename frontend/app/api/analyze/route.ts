import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.MARKET_API_URL || "http://8.159.141.123:8917";

export async function GET(req: NextRequest) {
  const slug = req.nextUrl.searchParams.get("slug");
  if (!slug) {
    return NextResponse.json({ detail: "slug is required" }, { status: 400 });
  }

  try {
    const res = await fetch(
      `${BACKEND_URL}/api/analyze?slug=${encodeURIComponent(slug)}`,
      { next: { revalidate: 0 } }
    );
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e) {
    return NextResponse.json(
      { detail: "Backend unreachable" },
      { status: 502 }
    );
  }
}
