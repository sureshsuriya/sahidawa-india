/**
 * apps/web/app/api/medicine/safety/route.ts
 *
 * Next.js API route that proxies GET /api/medicine/safety?q=<name>
 * to the Render backend API.
 *
 * Why this exists:
 *   The frontend calls /api/medicine/safety relative to the Vercel domain.
 *   Without this proxy, those requests hit Vercel and 404 because the
 *   Express server lives on Render (a different domain).
 *
 *   This proxy transparently forwards the request to Render, so:
 *   - No CORS issues (same-origin from the browser's perspective)
 *   - No need to set NEXT_PUBLIC_API_URL on Vercel
 *   - Works in local dev too (falls back to localhost:8080)
 */

import { NextRequest, NextResponse } from "next/server";

const RENDER_API =
    process.env.INTERNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const q = searchParams.get("q");

    if (!q || q.trim().length < 2) {
        return NextResponse.json(
            { error: "Query parameter 'q' is required (min 2 chars)." },
            { status: 400 }
        );
    }

    const upstreamUrl = `${RENDER_API}/api/medicine/safety?q=${encodeURIComponent(q.trim())}`;

    try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 30_000); // 30s — LLM can be slow on first call

        const upstream = await fetch(upstreamUrl, {
            headers: {
                Accept: "application/json",
                // Forward client IP for rate limiting on the Render side
                "X-Forwarded-For":
                    request.headers.get("x-forwarded-for") ??
                    request.headers.get("x-real-ip") ??
                    "anonymous",
            },
            signal: controller.signal,
        });

        clearTimeout(timer);

        const body = await upstream.text();

        return new NextResponse(body, {
            status: upstream.status,
            headers: {
                "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
                "X-Cache": upstream.headers.get("X-Cache") ?? "MISS",
                "X-Cache-Source": upstream.headers.get("X-Cache-Source") ?? "upstream",
                // Cache at the CDN/browser level for 1 hour (profile rarely changes)
                "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
            },
        });
    } catch (err) {
        const reason = err instanceof Error ? err.message : String(err);
        console.error("[medicine/safety proxy] upstream error:", reason);

        return NextResponse.json(
            {
                error: "Medicine safety data is temporarily unavailable. Please try again shortly.",
                code: "UPSTREAM_ERROR",
            },
            { status: 503 }
        );
    }
}
