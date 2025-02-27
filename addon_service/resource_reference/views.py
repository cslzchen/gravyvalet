from addon_service.common.permissions import SessionUserCanViewReferencedResource
from addon_service.common.viewsets import RestrictedReadOnlyViewSet
from addon_service.serializers import ResourceReferenceSerializer

from ..common.view_only_filter import ViewOnlyFilter
from .models import ResourceReference


class ResourceReferenceViewSet(RestrictedReadOnlyViewSet):
    queryset = ResourceReference.objects.all()
    serializer_class = ResourceReferenceSerializer
    permission_classes = [SessionUserCanViewReferencedResource]
    filter_backends = [ViewOnlyFilter]  # Ensures `view_only` is always allowed
    # Satisfies requirements of `RestrictedReadOnlyViewSet.list`
    required_list_filter_fields = ("resource_uri",)

    def get_query_parameters(self):
        params = super().get_query_parameters()
        params.add("view_only")  # Allow this custom parameter
        return params

    def get_queryset(self):
        queryset = super().get_queryset()
        if "view_only" in self.request.query_params:
            # Apply readonly logic if needed
            pass
        return queryset
