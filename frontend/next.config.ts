import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";
const backendOrigin = (process.env.BACKEND_ORIGIN ?? "http://localhost:8000").replace(/\/+$/, "");

// Nonce-based CSP (removing 'unsafe-inline' for scripts) is a Phase 13 hardening task.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,

  // Django URLs end with "/". Without this Next 308-redirects them to the slash-less form.
  skipTrailingSlashRedirect: true,

  async rewrites() {
    return [
      // Order matters: trailing-slash form first, then the fallback.
      { source: "/api/v1/:path*/", destination: `${backendOrigin}/api/v1/:path*/` },
      { source: "/api/v1/:path*", destination: `${backendOrigin}/api/v1/:path*` },
    ];
  },

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        ],
      },
    ];
  },
};

export default nextConfig;
