from rest_framework.filters import BaseFilterBackend


class URIFilter(BaseFilterBackend):

    def filter_queryset(self, request, queryset, view):
        if 'uris' in request.query_params:
            pass
        return queryset
