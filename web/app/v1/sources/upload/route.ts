import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

function apiBase() {
  return (
    process.env.API_INTERNAL_URL ||
    `http://127.0.0.1:${process.env.API_PORT || process.env.LYNOTE_API_PORT || "8000"}`
  );
}

export async function POST(request: NextRequest) {
  const contentType = request.headers.get("content-type") || "";
  const target = `${apiBase()}/v1/sources/upload`;
  const response = await fetch(target, {
    method: "POST",
    headers: contentType ? { "content-type": contentType } : undefined,
    body: request.body,
    duplex: "half",
  } as RequestInit);
  return new Response(response.body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "application/json",
    },
  });
}
