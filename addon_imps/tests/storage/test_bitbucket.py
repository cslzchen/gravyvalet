import unittest
from unittest.mock import (
    AsyncMock,
    Mock,
)

from addon_imps.storage.bitbucket import BitbucketStorageImp
from addon_toolkit.interfaces.storage import (
    ItemResult,
    ItemType,
    StorageConfig,
)


class TestBitbucketStorageImp(unittest.IsolatedAsyncioTestCase):
    BASE_URL = "https://api.bitbucket.org/2.0/"
    WORKSPACE = "workspace1"
    WORKSPACE_NAME = "Workspace One"
    WORKSPACE2 = "workspace2"
    WORKSPACE2_NAME = "Workspace Two"
    REPO = "repo1"
    REPO_NAME = "Repository One"
    REPO2 = "repo2"
    REPO2_NAME = "Repository Two"
    FILE_PATH = "path/to/file.txt"
    FILE_NAME = "file.txt"

    def setUp(self):
        self.config = StorageConfig(
            external_api_url=self.BASE_URL,
            max_upload_mb=100,
            connected_root_id="",
            external_account_id="",
        )
        self.network = Mock()
        self.network.GET = Mock()
        self.imp = BitbucketStorageImp(config=self.config, network=self.network)

    def _patch_get(
        self, endpoint: str, return_value: dict, status: int = 200, query: dict = None
    ):
        mock_response = AsyncMock()
        mock_response.json_content.return_value = return_value
        mock_response.http_status = status

        context_manager_mock = AsyncMock()
        context_manager_mock.__aenter__.return_value = mock_response
        context_manager_mock.__aexit__.return_value = None

        self.network.GET.return_value = context_manager_mock
        self.expected_get_call = (endpoint, query)

    def _assert_get_called_once(self):
        endpoint, query = self.expected_get_call
        if query is None:
            self.network.GET.assert_called_once_with(endpoint)
        else:
            self.network.GET.assert_called_once_with(endpoint, query=query)

    async def test_get_external_account_id(self):
        endpoint = "user"
        mock_response = {"uuid": "{user-uuid}"}
        self._patch_get(endpoint, mock_response)

        result = await self.imp.get_external_account_id({})

        self.assertEqual(result, "{user-uuid}")
        self._assert_get_called_once()

    async def test_get_external_account_id_no_uuid(self):
        endpoint = "user"
        mock_response = {}
        self._patch_get(endpoint, mock_response)

        with self.assertRaises(ValueError) as context:
            await self.imp.get_external_account_id({})

        self.assertIn("Failed to retrieve user UUID", str(context.exception))
        self._assert_get_called_once()

    async def test_list_root_items(self):
        endpoint = "user/permissions/workspaces"
        mock_response = {
            "values": [
                {
                    "workspace": {
                        "slug": self.WORKSPACE,
                        "name": self.WORKSPACE_NAME,
                    }
                },
                {
                    "workspace": {
                        "slug": self.WORKSPACE2,
                        "name": self.WORKSPACE2_NAME,
                    }
                },
            ],
            "next": f"{self.BASE_URL}user/permissions/workspaces?page=2",
        }
        query = {"pagelen": "100"}
        self._patch_get(endpoint, mock_response, query=query)
        expected_items = [
            ItemResult(
                item_id=f"workspace:{self.WORKSPACE}",
                item_name=self.WORKSPACE_NAME,
                item_type=ItemType.FOLDER,
                can_be_root=False,
            ),
            ItemResult(
                item_id=f"workspace:{self.WORKSPACE2}",
                item_name=self.WORKSPACE2_NAME,
                item_type=ItemType.FOLDER,
                can_be_root=False,
            ),
        ]

        result = await self.imp.list_root_items()

        self.assertEqual(result.items, expected_items)
        self.assertEqual(result.next_sample_cursor, mock_response["next"])
        self._assert_get_called_once()

    async def test_get_item_info(self):
        test_cases = [
            {
                "item_id": f"workspace:{self.WORKSPACE}",
                "endpoint": f"workspaces/{self.WORKSPACE}",
                "mock_response": {
                    "slug": self.WORKSPACE,
                    "name": self.WORKSPACE_NAME,
                },
                "expected_result": ItemResult(
                    item_id=f"workspace:{self.WORKSPACE}",
                    item_name=self.WORKSPACE_NAME,
                    item_type=ItemType.FOLDER,
                    can_be_root=False,
                ),
            },
            {
                "item_id": f"repository:{self.WORKSPACE}/{self.REPO}",
                "endpoint": f"repositories/{self.WORKSPACE}/{self.REPO}",
                "mock_response": {
                    "full_name": f"{self.WORKSPACE}/{self.REPO}",
                    "name": self.REPO_NAME,
                },
                "expected_result": ItemResult(
                    item_id=f"repository:{self.WORKSPACE}/{self.REPO}",
                    item_name=self.REPO_NAME,
                    item_type=ItemType.FOLDER,
                    can_be_root=True,
                ),
            },
            {
                "item_id": f"repository:{self.WORKSPACE}/{self.REPO}/{self.FILE_PATH}",
                "endpoint": f"repositories/{self.WORKSPACE}/{self.REPO}/src/HEAD/{self.FILE_PATH}",
                "mock_response": {
                    "type": "commit_file",
                    "path": self.FILE_PATH,
                },
                "expected_result": ItemResult(
                    item_id=f"repository:{self.WORKSPACE}/{self.REPO}/{self.FILE_PATH}",
                    item_name=self.FILE_NAME,
                    item_type=ItemType.FILE,
                    can_be_root=False,
                ),
            },
        ]
        for case in test_cases:
            with self.subTest(item_id=case["item_id"]):
                self.network.GET.reset_mock()
                self._patch_get(case["endpoint"], case["mock_response"])
                result = await self.imp.get_item_info(case["item_id"])
                self.assertEqual(result, case["expected_result"])
                self._assert_get_called_once()

    async def test_get_item_info_invalid_item_id(self):
        item_id = "invalid_item_id"
        with self.assertRaises(ValueError) as context:
            await self.imp.get_item_info(item_id)
        self.assertIn("Invalid item_id format", str(context.exception))

    async def test_get_item_info_unknown_item_type(self):
        item_id = "unknown_type:some_id"
        with self.assertRaises(ValueError) as context:
            await self.imp.get_item_info(item_id)
        self.assertIn("Unknown item type: unknown_type", str(context.exception))

    async def test_list_child_items(self):
        test_cases = [
            {
                "item_id": f"workspace:{self.WORKSPACE}",
                "endpoint": f"repositories/{self.WORKSPACE}",
                "mock_response": {
                    "values": [
                        {
                            "full_name": f"{self.WORKSPACE}/{self.REPO}",
                            "name": self.REPO_NAME,
                        },
                        {
                            "full_name": f"{self.WORKSPACE}/{self.REPO2}",
                            "name": self.REPO2_NAME,
                        },
                    ],
                    "next": f"{self.BASE_URL}repositories/{self.WORKSPACE}?page=2",
                },
                "query": {"role": "member", "pagelen": "100"},
                "expected_items": [
                    ItemResult(
                        item_id=f"repository:{self.WORKSPACE}/{self.REPO}",
                        item_name=self.REPO_NAME,
                        item_type=ItemType.FOLDER,
                        can_be_root=True,
                    ),
                    ItemResult(
                        item_id=f"repository:{self.WORKSPACE}/{self.REPO2}",
                        item_name=self.REPO2_NAME,
                        item_type=ItemType.FOLDER,
                        can_be_root=True,
                    ),
                ],
            },
            {
                "item_id": f"repository:{self.WORKSPACE}/{self.REPO}",
                "endpoint": f"repositories/{self.WORKSPACE}/{self.REPO}/src/HEAD/",
                "mock_response": {
                    "values": [
                        {
                            "type": "commit_directory",
                            "path": "src",
                        },
                        {
                            "type": "commit_file",
                            "path": "README.md",
                        },
                    ],
                    "next": None,
                },
                "query": {},
                "expected_items": [
                    ItemResult(
                        item_id=f"repository:{self.WORKSPACE}/{self.REPO}/src",
                        item_name="src",
                        item_type=ItemType.FOLDER,
                        can_be_root=False,
                    ),
                    ItemResult(
                        item_id=f"repository:{self.WORKSPACE}/{self.REPO}/README.md",
                        item_name="README.md",
                        item_type=ItemType.FILE,
                        can_be_root=False,
                    ),
                ],
            },
            {
                "item_id": f"repository:{self.WORKSPACE}/{self.REPO}/src",
                "endpoint": f"repositories/{self.WORKSPACE}/{self.REPO}/src/HEAD/src",
                "mock_response": {
                    "values": [
                        {
                            "type": "commit_file",
                            "path": "src/main.py",
                        },
                        {
                            "type": "commit_file",
                            "path": "src/utils.py",
                        },
                    ],
                    "next": None,
                },
                "query": {},
                "expected_items": [
                    ItemResult(
                        item_id=f"repository:{self.WORKSPACE}/{self.REPO}/src/main.py",
                        item_name="main.py",
                        item_type=ItemType.FILE,
                        can_be_root=False,
                    ),
                    ItemResult(
                        item_id=f"repository:{self.WORKSPACE}/{self.REPO}/src/utils.py",
                        item_name="utils.py",
                        item_type=ItemType.FILE,
                        can_be_root=False,
                    ),
                ],
            },
        ]
        for case in test_cases:
            with self.subTest(item_id=case["item_id"]):
                self.network.GET.reset_mock()
                self._patch_get(
                    case["endpoint"], case["mock_response"], query=case["query"]
                )
                result = await self.imp.list_child_items(case["item_id"])
                self.assertEqual(result.items, case["expected_items"])
                self.assertEqual(
                    result.next_sample_cursor, case["mock_response"]["next"]
                )
                self._assert_get_called_once()

    async def test_list_child_items_invalid_item_id(self):
        item_id = "invalid_item_id"
        with self.assertRaises(ValueError) as context:
            await self.imp.list_child_items(item_id)
        self.assertIn("Invalid item_id format", str(context.exception))

    async def test_list_child_items_unknown_item_type(self):
        item_id = "unknown_type:some_id"
        with self.assertRaises(ValueError) as context:
            await self.imp.list_child_items(item_id)
        self.assertIn(
            "Cannot list child items for item type unknown_type", str(context.exception)
        )

    async def test_build_wb_config_repository(self):
        self.imp.config = StorageConfig(
            external_api_url=self.BASE_URL,
            max_upload_mb=100,
            connected_root_id=f"repository:{self.WORKSPACE}/{self.REPO}",
            external_account_id="",
        )

        result = await self.imp.build_wb_config()

        expected_result = {
            "owner": self.WORKSPACE,
            "repo": self.REPO,
            "host": "api.bitbucket.org",
        }
        self.assertEqual(result, expected_result)

    async def test_build_wb_config_workspace(self):
        self.imp.config = StorageConfig(
            external_api_url=self.BASE_URL,
            max_upload_mb=100,
            connected_root_id=f"workspace:{self.WORKSPACE}",
            external_account_id="",
        )

        with self.assertRaises(ValueError) as context:
            await self.imp.build_wb_config()
        self.assertIn(
            "Selecting only a workspace is not allowed", str(context.exception)
        )

    async def test_handle_response_success(self):
        mock_response = AsyncMock()
        mock_response.http_status = 200
        mock_response.json_content.return_value = {"key": "value"}

        result = await self.imp._handle_response(mock_response)

        self.assertEqual(result, {"key": "value"})
        mock_response.json_content.assert_awaited_once()

    async def test_handle_response_error(self):
        mock_response = AsyncMock()
        mock_response.http_status = 400
        mock_response.json_content.return_value = {"error": {"message": "Bad Request"}}

        with self.assertRaises(ValueError) as context:
            await self.imp._handle_response(mock_response)

        self.assertIn("HTTP Error 400: Bad Request", str(context.exception))
        mock_response.json_content.assert_awaited_once()

    async def test_parse_item_id(self):
        item_id = f"repository:{self.WORKSPACE}/{self.REPO}/{self.FILE_PATH}"
        result = self.imp._parse_item_id(item_id)
        self.assertEqual(
            result, ("repository", f"{self.WORKSPACE}/{self.REPO}/{self.FILE_PATH}")
        )

    async def test_make_item_id(self):
        item_type = "repository"
        actual_id = f"{self.WORKSPACE}/{self.REPO}"
        result = self.imp._make_item_id(item_type, actual_id)
        self.assertEqual(result, f"repository:{self.WORKSPACE}/{self.REPO}")

    async def test_split_repo_full_name_and_path(self):
        actual_id = f"{self.WORKSPACE}/{self.REPO}/{self.FILE_PATH}"
        repo_full_name, path_param = self.imp._split_repo_full_name_and_path(actual_id)
        self.assertEqual(repo_full_name, f"{self.WORKSPACE}/{self.REPO}")
        self.assertEqual(path_param, self.FILE_PATH)

    async def test_params_from_cursor(self):
        cursor = f"{self.BASE_URL}repositories/{self.WORKSPACE}?page=2&pagelen=100"
        result = self.imp._params_from_cursor(cursor)
        self.assertEqual(result, {"page": "2", "pagelen": "100"})

    async def test_params_from_cursor_empty(self):
        cursor = ""
        result = self.imp._params_from_cursor(cursor)
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
