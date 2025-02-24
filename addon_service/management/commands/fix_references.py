import logging

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import (
    F,
    Func,
    Value,
)

from addon_service.resource_reference.models import ResourceReference
from addon_service.user_reference.models import UserReference
from app import settings


logger = logging.getLogger(__name__)

OSF_BASE = settings.OSF_API_BASE_URL.replace("192.168.168.167", "localhost").replace(
    "8000", "5000"
)
NEW_OSF_BASE = settings.OSF_BASE_URL.replace("192.168.168.167", "localhost")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--original",
            type=str,
            default=None,
        )
        parser.add_argument(
            "--replacement",
            type=str,
            default=None,
        )

    @transaction.atomic
    def handle(self, *args, **options):
        original = options["original"]
        replacement = options["replacement"]

        UserReference.objects.all().update(
            user_uri=Func(
                F("user_uri"),
                Value(original if original is not None else OSF_BASE),
                Value(replacement if replacement is not None else NEW_OSF_BASE),
                function="REPLACE",
            )
        )
        ResourceReference.objects.all().update(
            resource_uri=Func(
                F("resource_uri"),
                Value(original if original is not None else OSF_BASE),
                Value(replacement if replacement is not None else NEW_OSF_BASE),
                function="REPLACE",
            )
        )
