import { NextResponse, type NextRequest } from "next/server";

const BACKEND_ORIGIN = (process.env.BACKEND_ORIGIN ?? "http://localhost:8000").replace(/\/+$/, "");
const PROXY_SHARED_SECRET = process.env.PROXY_SHARED_SECRET ?? "";

/** Non-secret cookie set by the backend while a session probably exists (the refresh cookie is path-scoped
 *  to /api/v1/auth/, so page requests cannot see it). Real validation always happens on the API. */
const SESSION_HINT_COOKIE = "sid_hint";
const PUBLIC_PATHS = new Set(["/", "/login", "/register", "/forgot-password", "/reset-password", "/forbidden"]);

/** /api/v1/* -> Django. Forwards the real client IP, authenticated by a shared secret, because behind
 *  Vercel the backend only sees the proxy as its TCP peer. Client-supplied copies of these headers are dropped. */
function proxyToBackend(request: NextRequest) {
  const headers = new Headers(request.headers);
  headers.delete("x-client-ip");
  headers.delete("x-proxy-secret");

  const forwardedFor = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const clientIp = forwardedFor || request.headers.get("x-real-ip") || "";
  if (clientIp && PROXY_SHARED_SECRET) headers.set("x-client-ip", clientIp);
  if (PROXY_SHARED_SECRET) headers.set("x-proxy-secret", PROXY_SHARED_SECRET);

  const { pathname, search } = request.nextUrl;
  return NextResponse.rewrite(new URL(`${pathname}${search}`, BACKEND_ORIGIN), { request: { headers } });
}

/** Next.js 16 renamed middleware.ts to proxy.ts. Cheap redirect-only guard. It is a UX shortcut, not a security boundary: every API call is authorised by Django. */
function guardPage(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PATHS.has(pathname)) return NextResponse.next();
  if (request.cookies.get(SESSION_HINT_COOKIE)?.value) return NextResponse.next();

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  loginUrl.search = `?next=${encodeURIComponent(pathname)}`;
  return NextResponse.redirect(loginUrl);
}

export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/api/v1/")) return proxyToBackend(request);
  return guardPage(request);
}

export const config = {
  matcher: ["/api/v1/:path*", "/((?!api/|_next/|favicon.ico|.*\\..*).*)"],
};
