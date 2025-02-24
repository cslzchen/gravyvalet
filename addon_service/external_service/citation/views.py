from rest_framework_json_api.views import ReadOnlyModelViewSet

from .models import ExternalCitationService
from .serializers import ExternalCitationServiceSerializer


class ExternalCitationServiceViewSet(ReadOnlyModelViewSet):
    queryset = ExternalCitationService.objects.all().select_related(
        "oauth2_client_config", "oauth1_client_config"
    )
    serializer_class = ExternalCitationServiceSerializer
