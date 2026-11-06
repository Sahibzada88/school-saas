import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Pagination as PaginationInfo } from "@/types/api";

export function Pagination({
  pagination,
  onPageChange,
  disabled,
}: {
  pagination?: PaginationInfo;
  onPageChange: (page: number) => void;
  disabled?: boolean;
}) {
  if (!pagination || pagination.total === 0) return null;
  const { page, total_pages, total } = pagination;

  return (
    <div className="flex items-center justify-between gap-3 text-sm text-muted-foreground">
      <span>
        Page {page} of {total_pages} · {total} total
      </span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={disabled || page <= 1} onClick={() => onPageChange(page - 1)}>
          <ChevronLeft className="size-4" /> Previous
        </Button>
        <Button variant="outline" size="sm" disabled={disabled || page >= total_pages} onClick={() => onPageChange(page + 1)}>
          Next <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}
