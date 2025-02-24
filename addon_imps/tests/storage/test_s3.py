from unittest import IsolatedAsyncioTestCase
from unittest.mock import (
    MagicMock,
    create_autospec,
    patch,
)

from botocore.exceptions import ClientError
from django.core.exceptions import ValidationError

from addon_imps.storage.s3 import S3StorageImp
from addon_toolkit.credentials import AccessKeySecretKeyCredentials
from addon_toolkit.interfaces.storage import (
    ItemResult,
    ItemSampleResult,
    ItemType,
    StorageConfig,
)


class TestS3StorageImp(IsolatedAsyncioTestCase):
    def setUp(self):
        self.base_url = "https://google-drive-api.com"
        self.config = StorageConfig(external_api_url=self.base_url, max_upload_mb=123)
        self.client = MagicMock()
        self.credentials = AccessKeySecretKeyCredentials(
            access_key="123", secret_key="456"
        )
        self.imp = S3StorageImp(config=self.config, credentials=self.credentials)
        self.imp.client = self.client

    def test_list_buckets(self):
        self.client.list_buckets.return_value = {
            "Buckets": [
                {
                    "Name": "123",
                },
                {
                    "Name": "456",
                },
            ]
        }
        assert [
            ItemResult(item_name="123/", item_id="123:/", item_type=ItemType.FOLDER),
            ItemResult(item_name="456/", item_id="456:/", item_type=ItemType.FOLDER),
        ] == [*self.imp.list_buckets()]
        self.client.list_buckets.assert_called_once_with()

    @patch.object(S3StorageImp, "create_client")
    def test_confirm_credentials_success(self, create_client_mock):
        creds = AccessKeySecretKeyCredentials(access_key="123", secret_key="456")
        self.imp.confirm_credentials(creds)

        create_client_mock.assert_called_once_with(creds)
        create_client_mock.return_value.list_buckets.assert_called_once_with()

    @patch.object(S3StorageImp, "create_client")
    def test_confirm_credentials_fail(self, create_client_mock):
        creds = AccessKeySecretKeyCredentials(access_key="123", secret_key="456")
        create_client_mock.return_value.list_buckets.side_effect = ClientError(
            error_response={"Error": {"Code": "NoSuchBucket"}},
            operation_name="list_buckets",
        )
        with self.assertRaises(ValidationError):
            self.imp.confirm_credentials(creds)

        create_client_mock.assert_called_once_with(creds)
        create_client_mock.return_value.list_buckets.assert_called_once_with()

    @patch(f"{S3StorageImp.__module__}.boto3.client")
    def test_create_client(self, create_mock):
        creds = AccessKeySecretKeyCredentials(access_key="123", secret_key="456")
        self.imp.create_client(creds)
        create_mock.assert_called_once_with(
            "s3", aws_access_key_id="123", aws_secret_access_key="456"
        )

    async def test_list_root_items(self):
        items = [
            ItemResult(item_name="123/", item_id="123/", item_type=ItemType.FOLDER),
            ItemResult(item_name="456/", item_id="456/", item_type=ItemType.FOLDER),
        ]
        self.imp.list_buckets = create_autospec(
            self.imp.list_buckets, spec_set=True, return_value=iter(items)
        )
        assert await self.imp.list_root_items() == ItemSampleResult(
            items=items, total_count=2
        )
        self.imp.list_buckets.assert_called_once_with()
        self.client.head_bucket.assert_not_called()

    async def test_get_item_info_None(self):
        assert await self.imp.get_item_info(None) is None
        assert await self.imp.get_item_info("") is None
        assert await self.imp.get_item_info(" ") is None
        assert await self.imp.get_item_info("cwdasdasdasdsadas") is None
        self.client.head_bucket.assert_not_called()
        self.client.list_buckets.assert_not_called()

    async def test_get_item_info_in_bucket_one(self):
        self.client.list_objects.return_value = {
            "Contents": [
                {
                    "Key": "789",
                }
            ]
        }
        result = await self.imp.get_item_info("123:/456")

        self.client.list_objects.assert_called_once_with(
            Bucket="123",
            Prefix="456",
            Delimiter="/",
        )
        assert result == ItemResult(
            item_name="789", item_id="789", item_type=ItemType.FILE
        )
        self.client.head_bucket.assert_not_called()

    async def test_get_item_info_in_bucket_multiple(self):
        self.client.list_objects.return_value = {
            "Contents": [
                {
                    "Key": "789",
                },
                {
                    "Key": "32131213321",
                },
            ]
        }
        result = await self.imp.get_item_info("123:/456")

        self.client.list_objects.assert_called_once_with(
            Bucket="123",
            Prefix="456",
            Delimiter="/",
        )
        assert result == ItemResult(
            item_name="123:/456", item_id="123:/456", item_type=ItemType.FOLDER
        )
        self.client.head_bucket.assert_not_called()

    async def test_get_item_info_in_bucket_none(self):
        self.client.list_objects.return_value = {"Contents": []}
        result = await self.imp.get_item_info("123:/456")

        self.client.list_objects.assert_called_once_with(
            Bucket="123",
            Prefix="456",
            Delimiter="/",
        )
        assert result is None
        self.client.head_bucket.assert_not_called()

    async def test_get_item_info_in_bucket_none2(self):
        self.client.list_objects.return_value = {}
        result = await self.imp.get_item_info("123:/456")

        self.client.list_objects.assert_called_once_with(
            Bucket="123",
            Prefix="456",
            Delimiter="/",
        )
        assert result is None
        self.client.head_bucket.assert_not_called()

    async def test_get_item_info_bucket(self):
        result = await self.imp.get_item_info("123:/")

        self.client.head_bucket.assert_called_once_with(
            Bucket="123",
        )
        assert result == ItemResult(
            item_name="123/", item_id="123:/", item_type=ItemType.FOLDER
        )

    async def test_get_item_info_bucket_error(self):
        self.client.head_bucket.side_effect = ClientError(
            error_response={"Error": {"Code": "NoSuchBucket"}},
            operation_name="head_bucket",
        )
        result = await self.imp.get_item_info("123:/")

        self.client.head_bucket.assert_called_once_with(
            Bucket="123",
        )
        assert result is None

    async def test_list_child_items_fail(self):
        result = await self.imp.list_child_items("123")

        self.client.list_objects.assert_not_called()
        assert result is None

    async def test_list_child_items_success(self):
        self.client.list_objects.return_value = {
            "CommonPrefixes": [{"Prefix": "hello/"}],
            "Contents": [{"Key": "4324.htmx"}],
        }
        result = await self.imp.list_child_items("123:/")

        self.client.list_objects.assert_called_once_with(
            Bucket="123",
            Prefix="",
            Delimiter="/",
        )
        self.assertEqual(
            result,
            ItemSampleResult(
                items=[
                    ItemResult(
                        item_name="hello/",
                        item_id="123:/hello/",
                        item_type=ItemType.FOLDER,
                    ),
                    ItemResult(
                        item_name="4324.htmx",
                        item_id="123:/4324.htmx",
                        item_type=ItemType.FILE,
                    ),
                ],
                total_count=2,
            ),
        )

    async def test_list_child_items_folder(self):
        self.client.list_objects.return_value = {
            "CommonPrefixes": [{"Prefix": "hello/"}],
            "Contents": [{"Key": "4324.htmx"}],
        }
        result = await self.imp.list_child_items("123:/", item_type=ItemType.FOLDER)

        self.client.list_objects.assert_called_once_with(
            Bucket="123",
            Prefix="",
            Delimiter="/",
        )
        self.assertEqual(
            result,
            ItemSampleResult(
                items=[
                    ItemResult(
                        item_name="hello/",
                        item_id="123:/hello/",
                        item_type=ItemType.FOLDER,
                    ),
                ],
                total_count=1,
            ),
        )

    async def test_list_child_items_file(self):
        self.client.list_objects.return_value = {
            "CommonPrefixes": [{"Prefix": "hello/"}],
            "Contents": [{"Key": "4324.htmx"}],
        }
        result = await self.imp.list_child_items("123:/", item_type=ItemType.FILE)

        self.client.list_objects.assert_called_once_with(
            Bucket="123",
            Prefix="",
            Delimiter="/",
        )
        self.assertEqual(
            result,
            ItemSampleResult(
                items=[
                    ItemResult(
                        item_name="4324.htmx",
                        item_id="123:/4324.htmx",
                        item_type=ItemType.FILE,
                    ),
                ],
                total_count=1,
            ),
        )
