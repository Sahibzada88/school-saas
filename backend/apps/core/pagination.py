from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .responses import Envelope


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        paginator = self.page.paginator
        return Response(
            Envelope(
                success=True,
                message="",
                data={
                    "results": data,
                    "pagination": {
                        "page": self.page.number,
                        "page_size": paginator.per_page,
                        "total": paginator.count,
                        "total_pages": paginator.num_pages,
                    },
                },
            )
        )

    def get_paginated_response_schema(self, schema):  # keeps OpenAPI tooling honest later
        return {"type": "object", "properties": {"success": {"type": "boolean"}, "data": schema}}
