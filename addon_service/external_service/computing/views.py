from rest_framework_json_api.views import ReadOnlyModelViewSet

from .models import ExternalComputingService
from .serializers import ExternalComputingServiceSerializer


class ExternalComputingServiceViewSet(ReadOnlyModelViewSet):
    queryset = ExternalComputingService.objects.all().select_related(
        "oauth2_client_config"
    )
    serializer_class = ExternalComputingServiceSerializer
