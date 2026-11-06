/** Same-origin by default; Next.js rewrites this to the Django backend. */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "/api/v1").replace(/\/+$/, "");
