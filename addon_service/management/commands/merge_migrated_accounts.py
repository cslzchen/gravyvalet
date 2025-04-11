import logging

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import (
    Count,
    F,
)

from addon_service.authorized_account.citation.models import AuthorizedCitationAccount
from addon_service.authorized_account.computing.models import AuthorizedComputingAccount
from addon_service.authorized_account.storage.models import AuthorizedStorageAccount
from addon_service.osf_models.models import (
    ExternalAccount,
    UserToExternalAccount,
)


logger = logging.getLogger(__name__)

services = {
    "dropbox": "storage",
    "bitbucket": "storage",
    "box": "storage",
    "github": "storage",
    "googledrive": "storage",
    "figshare": "storage",
    "onedrive": "storage",
    "mendeley": "citations",
}


def get_class(integration_type):
    if integration_type == "storage":
        return AuthorizedStorageAccount
    elif integration_type == "citations":
        return AuthorizedCitationAccount
    elif integration_type == "computing":
        return AuthorizedComputingAccount
    else:
        raise


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--fake", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        shared_ids = (
            UserToExternalAccount.objects.values("externalaccount")
            .annotate(count=Count("osfuser"))
            .filter(count__gte=2)
        )
        shared_accounts = ExternalAccount.objects.filter(
            id__in=[item.get("externalaccount") for item in shared_ids],
            provider__in=services.keys(),
        )
        for account in shared_accounts:
            integration_type = services[account.provider]
            AuthorizedAccount = get_class(integration_type)
            accounts = (
                AuthorizedAccount.objects.filter(
                    external_account_id=account.provider_id,
                )
                .select_related(
                    "oauth2_token_metadata", "_credentials", "external_service"
                )
                .order_by(
                    F("oauth2_token_metadata__date_last_refreshed").desc(
                        nulls_last=True
                    )
                )
            )
            if accounts.count() < 2:
                logger.warning(
                    f"Found {accounts.count()} accounts for {account.provider} {account.provider_id}, skipping"
                )
                continue
            # take the first account here because it has the most recently refreshed credentials,
            # and update all credentials/token metadata with first_account's ones
            account = accounts[0]
            token_metadata = account.oauth2_token_metadata
            credentials = account._credentials
            logger.warning(
                f"Merging accounts that point to {account.external_service.external_service_name} with id {account.id}"
            )
            for account_to_update in accounts:
                last_refreshed = getattr(
                    account_to_update.oauth2_token_metadata,
                    "date_last_refreshed",
                    "NO_TOKEN_META",
                )
                creds_id = getattr(account_to_update._credentials, "id", "NO_CREDS")
                if account_to_update.id == account.id:
                    logger.warning(
                        f"Using credentials {creds_id} from {account_to_update.id} refreshed on {last_refreshed}"
                    )
                else:
                    logger.warning(
                        f"Updating {account_to_update.id} refreshed on {last_refreshed}, removing {creds_id}"
                    )

            accounts.update(
                oauth2_token_metadata=token_metadata, _credentials=credentials
            )
        if options.get("fake"):
            transaction.set_rollback(True)
