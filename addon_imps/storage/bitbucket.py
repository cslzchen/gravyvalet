import dataclasses
from urllib.parse import (
    parse_qs,
    urlparse,
)

from addon_toolkit.cursor import Cursor
from addon_toolkit.interfaces import storage


class NextLinkCursor(Cursor):
    def __init__(self, next_link: str | None):
        self._next_link = next_link

    @property
    def this_cursor_str(self) -> str:
        return ""

    @property
    def next_cursor_str(self) -> str | None:
        return self._next_link

    @property
    def prev_cursor_str(self) -> str | None:
        return None

    @property
    def first_cursor_str(self) -> str:
        return ""


@dataclasses.dataclass
class BitbucketStorageImp(storage.StorageAddonHttpRequestorImp):
    async def get_external_account_id(self, auth_result_extras: dict[str, str]) -> str:
        async with self.network.GET("user") as response:
            json_data = await self._handle_response(response)
            uuid = json_data.get("uuid")
            if not uuid:
                raise ValueError("Failed to retrieve user UUID")
        return uuid

    async def build_wb_config(self) -> dict:
        if not self.config.connected_root_id:
            raise ValueError(
                "connected_root_id is not set. Cannot build WaterButler config."
            )
        item_type_str, actual_id = self._parse_item_id(self.config.connected_root_id)
        if item_type_str == "repository":
            workspace_slug, repo_slug = actual_id.split("/", 1)
            return {
                "owner": workspace_slug,
                "repo": repo_slug,
                "host": "api.bitbucket.org",
            }
        elif item_type_str == "workspace":
            raise ValueError(
                "Selecting only a workspace is not allowed. Please choose a repository."
            )
        else:
            raise ValueError(
                f"Unsupported item type for build_wb_config: {item_type_str}"
            )

    async def list_root_items(self, page_cursor: str = "") -> storage.ItemSampleResult:
        params = self._params_from_cursor(page_cursor)
        params["pagelen"] = "100"
        endpoint = "user/permissions/workspaces"
        try:
            async with self.network.GET(endpoint, query=params) as response:
                json_data = await self._handle_response(response)
        except Exception as e:
            raise ValueError(f"Failed to fetch workspaces: {e}")
        items = []
        for workspace in json_data.get("values", []):
            slug = workspace["workspace"]["slug"]
            name = workspace["workspace"].get("name") or slug
            item_id = self._make_item_id("workspace", slug)
            items.append(
                storage.ItemResult(
                    item_id=item_id,
                    item_name=name,
                    item_type=storage.ItemType.FOLDER,
                    can_be_root=False,
                )
            )
        return self._create_item_sample_result(items, json_data)

    async def get_item_info(self, item_id: str) -> storage.ItemResult:
        if not item_id:
            raise ValueError("Item ID is empty.")
        item_type_str, actual_id = self._parse_item_id(item_id)
        if item_type_str == "workspace":
            endpoint = f"workspaces/{actual_id}"
            async with self.network.GET(endpoint) as response:
                json_data = await self._handle_response(response)
                name = json_data.get("name") or actual_id
                return storage.ItemResult(
                    item_id=item_id,
                    item_name=name,
                    item_type=storage.ItemType.FOLDER,
                    can_be_root=False,
                )
        elif item_type_str == "repository":
            repo_full_name, path_param = self._split_repo_full_name_and_path(actual_id)
            if not path_param:
                endpoint = f"repositories/{repo_full_name}"
                async with self.network.GET(endpoint) as response:
                    json_data = await self._handle_response(response)
                    name = json_data.get("name") or repo_full_name
                    return storage.ItemResult(
                        item_id=item_id,
                        item_name=name,
                        item_type=storage.ItemType.FOLDER,
                    )
            else:
                endpoint = f"repositories/{repo_full_name}/src/HEAD/{path_param}"
                async with self.network.GET(endpoint) as response:
                    json_data = await self._handle_response(response)
                    item_type_value = (
                        storage.ItemType.FOLDER
                        if json_data.get("type") == "commit_directory"
                        else storage.ItemType.FILE
                    )
                    item_name = path_param.split("/")[-1] or "Unnamed Item"
                    return storage.ItemResult(
                        item_id=item_id,
                        item_name=item_name,
                        item_type=item_type_value,
                        can_be_root=False,
                    )
        else:
            raise ValueError(f"Unknown item type: {item_type_str}")

    async def list_child_items(
        self,
        item_id: str,
        page_cursor: str = "",
        item_type: storage.ItemType | None = None,
    ) -> storage.ItemSampleResult:
        if not item_id:
            raise ValueError("Item ID is empty.")
        item_type_str, actual_id = self._parse_item_id(item_id)
        params = self._params_from_cursor(page_cursor)
        if item_type_str == "workspace":
            return await self._list_workspace_child_items(actual_id, params, item_type)
        elif item_type_str == "repository":
            return await self._list_repository_child_items(actual_id, params, item_type)
        else:
            raise ValueError(f"Cannot list child items for item type {item_type_str}")

    async def _list_workspace_child_items(
        self,
        actual_id: str,
        params: dict[str, str],
        item_type: storage.ItemType | None = None,
    ) -> storage.ItemSampleResult:
        workspace_slug = actual_id
        params["role"] = "member"
        params["pagelen"] = "100"
        endpoint = f"repositories/{workspace_slug}"
        try:
            async with self.network.GET(endpoint, query=params) as response:
                json_data = await self._handle_response(response)
        except Exception as e:
            raise ValueError(f"Failed to fetch repositories: {e}")
        items = []
        for repo in json_data.get("values", []):
            full_name = repo.get("full_name")
            name = repo.get("name") or "Unnamed Repository"
            if not full_name:
                continue
            item_id = self._make_item_id("repository", full_name)
            items.append(
                storage.ItemResult(
                    item_id=item_id, item_name=name, item_type=storage.ItemType.FOLDER
                )
            )
        return self._create_item_sample_result(items, json_data)

    async def _list_repository_child_items(
        self,
        actual_id: str,
        params: dict[str, str],
        item_type: storage.ItemType | None = None,
    ) -> storage.ItemSampleResult:
        repo_full_name, path_param = self._split_repo_full_name_and_path(actual_id)
        endpoint = f"repositories/{repo_full_name}/src/HEAD/{path_param}"
        try:
            async with self.network.GET(endpoint, query=params) as response:
                json_data = await self._handle_response(response)
        except Exception as e:
            raise ValueError(f"Failed to list child items: {e}")
        items = []
        for item in json_data.get("values", []):
            item_type_value = (
                storage.ItemType.FOLDER
                if item["type"] == "commit_directory"
                else storage.ItemType.FILE
            )
            if item_type is not None and item_type != item_type_value:
                continue
            path = item.get("path")
            if not path:
                continue
            item_name = path.split("/")[-1] or "Unnamed Item"
            item_id_value = self._make_item_id("repository", f"{repo_full_name}/{path}")
            items.append(
                storage.ItemResult(
                    item_id=item_id_value,
                    item_name=item_name,
                    item_type=item_type_value,
                    can_be_root=False,
                )
            )
        return self._create_item_sample_result(items, json_data)

    def _create_item_sample_result(
        self,
        items: list[storage.ItemResult],
        json_data: dict,
    ) -> storage.ItemSampleResult:
        result = storage.ItemSampleResult(items=items)
        next_cursor = json_data.get("next")
        cursor = NextLinkCursor(next_link=next_cursor)
        return result.with_cursor(cursor)

    def _split_repo_full_name_and_path(self, actual_id: str) -> tuple[str, str]:
        parts = actual_id.split("/", 2)
        if len(parts) < 2:
            raise ValueError(
                "Invalid actual_id format. Expected 'workspace/repo_slug' or 'workspace/repo_slug/path/to/item'."
            )
        repo_full_name = f"{parts[0]}/{parts[1]}"
        path_param = parts[2] if len(parts) > 2 else ""
        return repo_full_name, path_param

    def _params_from_cursor(self, cursor: str = "") -> dict[str, str]:
        if not cursor:
            return {}
        parsed_url = urlparse(cursor)
        query_params = parse_qs(parsed_url.query)
        flat_query_params = {k: v[0] for k, v in query_params.items()}
        return flat_query_params

    def _make_item_id(self, item_type: str, item_id: str) -> str:
        return f"{item_type}:{item_id}"

    def _parse_item_id(self, item_id: str) -> tuple[str, str]:
        if not item_id:
            raise ValueError("Item ID is empty.")
        try:
            _type_str, actual_id = item_id.split(":", 1)
            return _type_str, actual_id
        except ValueError:
            raise ValueError(f"Invalid item_id format: {item_id!r}")

    async def _handle_response(self, response) -> dict:
        if response.http_status >= 400:
            json_data = await response.json_content()
            error_message = json_data.get("error", {}).get("message", "Unknown error")
            raise ValueError(f"HTTP Error {response.http_status}: {error_message}")
        return await response.json_content()
