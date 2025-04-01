from django.core.exceptions import ValidationError
from django.db import models

from addon_service.configured_addon.models import ConfiguredAddon
from addon_toolkit.interfaces.link import SupportedResourceTypes


def is_supported_resource_type(resource_type: int):
    try:
        resource_type = SupportedResourceTypes(resource_type)
        if len(resource_type) != 1:
            raise ValidationError("One may select only one resource type")
    except ValueError:
        raise ValidationError("Invalid resource type")


class ConfiguredLinkAddon(ConfiguredAddon):

    target_uri = models.URLField()
    target_id = models.CharField()
    int_resource_type = models.IntegerField(validators=[is_supported_resource_type])

    @property
    def resource_type(self) -> str:
        return SupportedResourceTypes(self.int_resource_type).name

    class Meta:
        verbose_name = "Configured Link Addon"
        verbose_name_plural = "Configured Link Addons"
        app_label = "addon_service"

    class JSONAPIMeta:
        resource_name = "configured-link-addons"
