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
    BitbucketNodeSettings,
    BitbucketUserSettings,
    BoxNodeSettings,
    BoxUserSettings,
    DropboxNodeSettings,
    DropboxUserSettings,
    ExternalAccount,
    FigshareNodeSettings,
    FigshareUserSettings,
    GithubNodeSettings,
    GithubUserSettings,
    GoogleDriveNodeSettings,
    GoogleDriveUserSettings,
    MendeleyNodeSettings,
    MendeleyUserSettings,
    OneDriveNodeSettings,
    OneDriveUserSettings,
    UserToExternalAccount,
)


logger = logging.getLogger(__name__)


def fetch_external_accounts(user_id: int, provider: str):
    return [
        obj.externalaccount
        for obj in UserToExternalAccount.objects.select_related(
            "externalaccount"
        ).filter(osfuser_id=user_id)
        if obj.externalaccount.provider == provider
    ]


services = {
    "dropbox": ["storage", DropboxUserSettings, DropboxNodeSettings],
    "bitbucket": ["storage", BitbucketUserSettings, BitbucketNodeSettings],
    "box": ["storage", BoxUserSettings, BoxNodeSettings],
    "github": ["storage", GithubUserSettings, GithubNodeSettings],
    "googledrive": ["storage", GoogleDriveUserSettings, GoogleDriveNodeSettings],
    "figshare": ["storage", FigshareUserSettings, FigshareNodeSettings],
    "onedrive": ["storage", OneDriveUserSettings, OneDriveNodeSettings],
    "mendeley": ["citations", MendeleyUserSettings, MendeleyNodeSettings],
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
            integration_type = services[account.provider][0]
            AuthorizedAccount = get_class(integration_type)
            accounts = (
                AuthorizedAccount.objects.filter(
                    external_account_id=account.provider_id,
                )
                .select_related("oauth2_token_metadata", "_credentials")
                .order_by(
                    F("oauth2_token_metadata__date_last_refreshed").desc(
                        nulls_last=True
                    )
                )
            )
            token_metadata = accounts[0].oauth2_token_metadata
            credentials = accounts[0]._credentials
            accounts.update(
                oauth2_token_metadata=token_metadata, _credentials=credentials
            )
