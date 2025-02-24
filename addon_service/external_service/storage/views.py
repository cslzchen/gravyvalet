from rest_framework_json_api.views import ReadOnlyModelViewSet

from .models import ExternalStorageService
from .serializers import ExternalStorageServiceSerializer


class ExternalStorageServiceViewSet(ReadOnlyModelViewSet):
    queryset = ExternalStorageService.objects.all().select_related(
        "oauth2_client_config"
    )
    serializer_class = ExternalStorageServiceSerializer
