import logging

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Count

from addon_service.authorized_account.citation.models import AuthorizedCitationAccount
from addon_service.authorized_account.storage.models import AuthorizedStorageAccount
from addon_service.common.credentials_formats import CredentialsFormats
from addon_service.configured_addon.citation.models import ConfiguredCitationAddon
from addon_service.configured_addon.storage.models import ConfiguredStorageAddon
from addon_service.external_service.models import ExternalService
from addon_service.osf_models.models import (
    BitbucketUserSettings,
    BoxUserSettings,
    DataverseUserSettings,
    DropboxUserSettings,
    ExternalAccount,
    FigshareUserSettings,
    GithubUserSettings,
    GitlabUserSettings,
    GoogleDriveUserSettings,
    Guid,
    MendeleyUserSettings,
    OneDriveUserSettings,
    OsfUser,
    OwnCloudUserSettings,
    S3UserSettings,
    UserToExternalAccount,
    ZoteroUserSettings,
)
from addon_service.resource_reference.models import ResourceReference
from addon_service.user_reference.models import UserReference
from addon_toolkit import AddonCapabilities
from addon_toolkit.credentials import (
    AccessKeySecretKeyCredentials,
    AccessTokenCredentials,
    OAuth1Credentials,
    UsernamePasswordCredentials,
)
from app import settings


logger = logging.getLogger(__name__)

provider_to_user_settings = {
    "dropbox": DropboxUserSettings,
    "bitbucket": BitbucketUserSettings,
    "box": BoxUserSettings,
    "github": GithubUserSettings,
    "googledrive": GoogleDriveUserSettings,
    "gitlab": GitlabUserSettings,
    "dataverse": DataverseUserSettings,
    "owncloud": OwnCloudUserSettings,
    "figshare": FigshareUserSettings,
    "onedrive": OneDriveUserSettings,
    "s3": S3UserSettings,
    "mendeley": MendeleyUserSettings,
    "zotero": ZoteroUserSettings,
}
storage_provider = [
    "dropbox",
    "bitbucket",
    "box",
    "github",
    "googledrive",
    "gitlab",
    "dataverse",
    "owncloud",
    "figshare",
    "onedrive",
    "s3",
]
citation_provider = ["mendeley", "zotero"]

OSF_BASE = settings.OSF_BASE_URL.replace("192.168.168.167", "localhost").replace(
    "8000", "5000"
)


class CredentialException(Exception):
    pass


# Ported over from migrate_authorized_account.py
def get_credentials(
    external_service: ExternalService, external_account: ExternalAccount
):
    if external_service.credentials_format == CredentialsFormats.ACCESS_KEY_SECRET_KEY:
        check_fields(external_account, ["oauth_key", "oauth_secret"])
        credentials = AccessKeySecretKeyCredentials(
            access_key=external_account.oauth_key,
            secret_key=external_account.oauth_secret,
        )
    elif external_service.credentials_format == CredentialsFormats.USERNAME_PASSWORD:
        check_fields(external_account, ["display_name", "oauth_key"])
        credentials = UsernamePasswordCredentials(
            username=external_account.display_name, password=external_account.oauth_key
        )
    elif external_service.credentials_format == CredentialsFormats.OAUTH1A:
        check_fields(external_account, ["oauth_key", "oauth_secret"])
        credentials = OAuth1Credentials(
            oauth_token=external_account.oauth_key,
            oauth_token_secret=external_account.oauth_secret,
        )
    elif external_service.wb_key == "dataverse":
        check_fields(external_account, ["oauth_secret"])
        credentials = AccessTokenCredentials(access_token=external_account.oauth_secret)
    elif external_service.wb_key == "dropbox" and not external_account.refresh_token:
        check_fields(external_account, ["oauth_key"])
        credentials = AccessTokenCredentials(access_token=external_account.oauth_key)
    else:
        check_fields(external_account, ["oauth_key"])
        credentials = AccessTokenCredentials(access_token=external_account.oauth_key)
    return credentials


# Ported over from migrate_authorized_account.py
def check_fields(external_account: ExternalAccount, fields: list[str]):
    errors = []
    for field in fields:
        if getattr(external_account, field, None) is None:
            error_string = f"Required field <<{field}>> is None"
            errors.append(error_string)
    if errors:
        raise CredentialException(errors)


# Ported over from migrate_authorized_account.py
def get_node_guid(id_):
    content_type_id = cache.get_or_set(
        "node_contenttype_id",
        lambda: ContentType.objects.using("osf")
        .get(app_label="osf", model="abstractnode")
        .id,
        timeout=None,
    )
    return (
        Guid.objects.filter(content_type_id=content_type_id, object_id=id_).first()._id
    )


# return a list of tuples of (user_guid, provider_name_with_duplicate_accounts)
def get_target_user_pks_and_provider():
    return (
        UserToExternalAccount.objects.values("osfuser_id", "externalaccount__provider")
        .annotate(account_per_provider=Count("id"))
        .filter(account_per_provider__gt=1)
        .values_list("osfuser_id", "externalaccount__provider")
    )


def get_node_settings_for_user_and_provider(user, provider):
    UserSettings = provider_to_user_settings[provider]
    user_setting = UserSettings.objects.get(owner_id=user.id)
    return getattr(user_setting, f"{provider}nodesettings_set").all()


def get_configured_addon(node_guid, provider):
    resource_reference = ResourceReference.objects.get_or_create(
        resource_uri=f"{OSF_BASE}/{node_guid}"
    )[0]
    external_service = get_external_service(provider)
    if provider in storage_provider:
        ConfiguredAddon = ConfiguredStorageAddon
    elif provider in citation_provider:
        ConfiguredAddon = ConfiguredCitationAddon

    try:
        configured_addon = ConfiguredAddon.objects.get(
            authorized_resource=resource_reference,
            base_account__external_service=external_service,
        )
    except ConfiguredAddon.DoesNotExist:
        print("ConfiguredAddon not found")

    return configured_addon


def get_external_service(provider):
    return ExternalService.objects.get(wb_key=provider)


def get_user_reference(user_guid):
    return UserReference.objects.get_or_create(user_uri=f"{OSF_BASE}/{user_guid}")[0]


def get_or_create_authorized_account(external_account, provider, user_guid):
    if provider in storage_provider:
        AuthorizedAccount = AuthorizedStorageAccount
    elif provider in citation_provider:
        AuthorizedAccount = AuthorizedCitationAccount

    external_service = get_external_service(provider)
    account_owner = get_user_reference(user_guid)

    authorized_account = None
    if not AuthorizedAccount.objects.filter(
        external_account_id=external_account.id,
        external_service=external_service,
        account_owner=account_owner,
    ).exists():
        credentials = get_credentials(external_service, external_account)
        authorized_account = AuthorizedAccount(
            display_name=external_service.display_name.capitalize(),
            int_authorized_capabilities=(
                AddonCapabilities.UPDATE | AddonCapabilities.ACCESS
            ).value,
            account_owner=account_owner,
            external_service=external_service,
            credentials=credentials,
            external_account_id=external_account.provider_id,
        )
        authorized_account.save()
        print(f"\t\t\t\t Created AuthorizedAccount on {provider} for user {user_guid}")
    else:
        authorized_account = AuthorizedAccount.objects.get(
            external_account_id=external_account.id,
            external_service=external_service,
            account_owner=account_owner,
        )
        print(f"\t\t\t\t Found AuthorizedAccount on {provider} for user {user_guid}")

    return authorized_account


# check to see if the ConfiguredAddon's base account has the same
# external_account_id as the ExternalAccount's provider_id
def configured_addon_has_correct_base_account(external_account, node_guid, provider):
    configured_addon = get_configured_addon(node_guid, provider)
    if (
        configured_addon.base_account.external_account_id
        == external_account.provider_id
    ):
        return True
    print("\t\t\t Mismatch found:")
    print(
        f"\t\t\t\t ConfiguredAddon for node {node_guid} has base account external_account_id={configured_addon.base_account.external_account_id}, it should be {external_account.provider_id}"
    )
    return False


def fix_migration_for_user_and_provider(user, provider):
    if not user:
        return

    ns = get_node_settings_for_user_and_provider(user, provider)
    print(f"\t Found {ns.count()} NodeSettings for user {user.guid} on {provider}")
    for node_settings in ns:
        external_account = node_settings.external_account
        node_guid = get_node_guid(node_settings.owner_id)
        print(f"\t\t Checking node setting for node {node_guid}")
        # check to see if the migrated configured_addon instance have the authorized account with the same external_account_id
        if not configured_addon_has_correct_base_account(
            external_account, node_guid, provider
        ):
            # if not, then we fix it
            configured_addon = get_configured_addon(node_guid, provider)
            authorized_account = get_or_create_authorized_account(
                external_account, provider, user.guid
            )
            configured_addon.base_account = authorized_account
            configured_addon.save()
            print(f"\t\t\t Fixed mismatch for {provider} on {node_guid}")


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("--fake", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        fake = options["fake"]

        for user_pk, provider in get_target_user_pks_and_provider():
            user = OsfUser.objects.get(pk=user_pk)
            print(f"Found multiple ExternalAccount on {provider} for user {user.guid}")
            if provider != "boa":
                # We don't need to fix boa
                fix_migration_for_user_and_provider(user, provider)
        if fake:
            print("Rolling back the transactions because this is a fake run")
            transaction.set_rollback(True)
