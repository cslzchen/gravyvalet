from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django.db import models

from addon_service.configured_addon.models import ConfiguredAddon
from addon_toolkit.interfaces.link import (
    LinkConfig,
    SupportedResourceTypes,
)
from app.celery import app


def is_supported_resource_type(resource_type: int):
    try:
        resource_type = SupportedResourceTypes(resource_type)
        if len(resource_type) != 1:
            raise ValidationError("One may select only one resource type")
    except ValueError:
        raise ValidationError("Invalid resource type")


class ConfiguredLinkAddon(ConfiguredAddon):
    target_id = models.CharField()
    int_resource_type = models.BigIntegerField(validators=[is_supported_resource_type])

    @property
    def resource_type(self) -> SupportedResourceTypes:
        return SupportedResourceTypes(self.int_resource_type)

    @resource_type.setter
    def resource_type(self, value) -> None:
        self.int_resource_type = value.value

    def save(self, *args, full_clean=True, **kwargs):
        super().save(*args, full_clean=full_clean, **kwargs)
        app.send_task(
            "website.identifiers.tasks.task__update_doi_metadata_with_verified_links",
            kwargs={"target_guid": self.authorized_resource.guid},
        )

    def target_url(self):
        if self.target_id:
            from addon_service.addon_imp.instantiation import (
                get_link_addon_instance__blocking,
            )

            addon = get_link_addon_instance__blocking(
                self.imp_cls, self.base_account, self.config
            )
            return async_to_sync(addon.build_url_for_id)(self.target_id)

    @property
    def config(self) -> LinkConfig:
        return self.base_account.authorizedlinkaccount.config

    class Meta:
        verbose_name = "Configured Link Addon"
        verbose_name_plural = "Configured Link Addons"
        app_label = "addon_service"

    class JSONAPIMeta:
        resource_name = "configured-link-addons"
