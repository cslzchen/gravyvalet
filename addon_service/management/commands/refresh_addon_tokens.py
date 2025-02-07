import math
import time

import celery
from celery.utils.log import get_task_logger
from dateutil.relativedelta import relativedelta
from django.core.management import BaseCommand
from django.utils import timezone

from addon_service.authorized_account.models import AuthorizedAccount
from addon_service.external_service.models import ExternalService


logger = get_task_logger(__name__)


def get_authorized_accounts(delta, external_service):
    return AuthorizedAccount.objects.filter(
        external_service=external_service,
        oauth2_token_metadata__access_token_expiration__lt=timezone.now() - delta,
        oauth2_token_metadata__date_last_refreshed__lt=timezone.now() - delta,
    )


def refresh_addon_tokens_for_external_service(
    delta, external_service, rate_limit, fake
):
    allowance = rate_limit[0]
    last_call = time.time()
    for account in get_authorized_accounts(delta, external_service):
        logger.info(
            "Refreshing tokens on AuthorizedAccount {}; expires at {}".format(
                account.__repr__(),
                account.oauth2_token_metadata.access_token_expiration.strftime("%c"),
            )
        )
        if not fake:
            if allowance < 1:
                try:
                    time.sleep(rate_limit[1] - (time.time() - last_call))
                except (ValueError, OSError):
                    pass  # Value/IOError indicates negative sleep time in Py 3.5/2.7, respectively
                allowance = rate_limit[0]

            allowance -= 1
            last_call = time.time()
            account.refresh_oauth_access_token__blocking()


@celery.shared_task
def refresh_addon_tokens(addons=None, rate_limit=(5, 1), fake=True):
    for addon in addons:
        days = math.ceil(int(addons[addon]) * 0.75)
        delta = relativedelta(days=days)
        external_service = ExternalService.objects.get(wb_key=addon)
        if not external_service:
            logger.error(f"Unable to find ExternalService for addon {addon}")
        else:
            refresh_addon_tokens_for_external_service(
                delta, external_service, rate_limit, fake=fake
            )


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("--fake", action="store_true")

    def handle(self, *args, **options):
        fake = options["fake"]
        refresh_addon_tokens(addons=["box", "googledrive", "mendeley"], fake=fake)
