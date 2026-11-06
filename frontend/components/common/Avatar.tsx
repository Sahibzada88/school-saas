import { cn } from "@/lib/utils";

export function Avatar({ name, url, className }: { name: string; url?: string | null; className?: string }) {
  const initials = name.split(" ").filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("");
  return url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt="" className={cn("size-9 rounded-full border object-cover", className)} />
  ) : (
    <span aria-hidden className={cn("flex size-9 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground", className)}>{initials || "?"}</span>
  );
}
