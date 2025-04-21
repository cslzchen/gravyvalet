from addon_service.common.exceptions import (
    ItemNotFound,
    UnexpectedAddonError,
)
from addon_toolkit.cursor import Cursor
from addon_toolkit.interfaces import storage
from addon_toolkit.interfaces.storage import ItemType


class PageCursor(Cursor):
    def __init__(
        self,
        this_cursor_str: str,
        next_cursor_str: str | None = None,
        prev_cursor_str: str | None = None,
        first_cursor_str: str | None = None,
    ):
        self._this_cursor_str = this_cursor_str
        self._next_cursor_str = next_cursor_str
        self._prev_cursor_str = prev_cursor_str
        self._first_cursor_str = first_cursor_str

    @property
    def this_cursor_str(self) -> str:
        return self._this_cursor_str

    @property
    def next_cursor_str(self) -> str | None:
        return self._next_cursor_str

    @property
    def prev_cursor_str(self) -> str | None:
        return self._prev_cursor_str

    @property
    def first_cursor_str(self) -> str | None:
        return self._first_cursor_str


ITEM_TYPE_MAP = {
    ItemType.FILE: "file",
    ItemType.FOLDER: "dir",
}


class GitHubStorageImp(storage.StorageAddonHttpRequestorImp):
    """storage on GitHub

    see https://docs.github.com/en/rest
    """

    async def get_external_account_id(self, auth_result_extras: dict[str, str]) -> str:
        async with self.network.GET("user") as response:
            json = await response.json_content()
            return str(json["id"])

    def _parse_page(self, page_cursor: str) -> int:
        try:
            page = int(page_cursor)
        except ValueError:
            page = 1
        return page if page > 0 else 1

    async def list_root_items(self, page_cursor: str = "") -> storage.ItemSampleResult:
        page = self._parse_page(page_cursor)
        per_page = 30
        async with self.network.GET(
            "user/repos", query={"page": str(page), "per_page": str(per_page)}
        ) as response:
            if response.http_status == 200:
                json = await response.json_content()
                items = [self._parse_github_repo(repo) for repo in json]
                next_page = str(page + 1) if len(items) == per_page else None
                return storage.ItemSampleResult(
                    items=items, total_count=len(items)
                ).with_cursor(
                    PageCursor(
                        this_cursor_str=str(page),
                        next_cursor_str=next_page,
                        prev_cursor_str=str(page - 1) if page > 1 else None,
                        first_cursor_str="1",
                    )
                )
            elif response.http_status == 404:
                raise ItemNotFound
            else:
                raise UnexpectedAddonError

    async def build_wb_config(self) -> dict:
        owner, repo, _ = self._parse_github_item_id(self.config.connected_root_id)
        return {
            "owner": owner,
            "repo": repo,
        }

    async def get_item_info(self, item_id: str) -> storage.ItemResult:
        if item_id == "." or not item_id:
            return storage.ItemResult(
                item_id="",
                item_name="GitHub",
                item_type=ItemType.FOLDER,
            )
        owner, repo, path = self._parse_github_item_id(item_id)
        if path == "":
            url = f"repos/{owner}/{repo}"
        else:
            url = f"repos/{owner}/{repo}/contents/{path}"
        async with self.network.GET(url) as response:
            if response.http_status == 200:
                json = await response.json_content()
                if path != "":
                    if isinstance(json, dict):
                        return self._parse_github_item(json, full_name=item_id)
                    else:
                        return self._parse_github_item(json[0], full_name=item_id)
                else:
                    return self._parse_github_repo(json)
            elif response.http_status == 404:
                raise ItemNotFound
            else:
                raise UnexpectedAddonError

    async def list_child_items(
        self,
        item_id: str,
        page_cursor: str = "",
        item_type: storage.ItemType | None = None,
    ) -> storage.ItemSampleResult:
        owner, repo, path = self._parse_github_item_id(item_id)
        page = self._parse_page(page_cursor)
        per_page = 30
        async with self.network.GET(
            f"repos/{owner}/{repo}/contents/{path}",
            query={"page": str(page), "per_page": str(per_page)},
        ) as response:
            if response.http_status == 200:
                json = await response.json_content()
                git_hub_item_type = ITEM_TYPE_MAP[item_type] if item_type else None
                items = [
                    self._parse_github_item(entry, full_name=item_id)
                    for entry in json
                    if not git_hub_item_type or entry["type"] == git_hub_item_type
                ]
                next_page = str(page + 1) if len(items) == per_page else None

                return storage.ItemSampleResult(
                    items=items, total_count=len(items)
                ).with_cursor(
                    PageCursor(
                        this_cursor_str=str(page),
                        next_cursor_str=next_page,
                        prev_cursor_str=str(page - 1) if page > 1 else None,
                        first_cursor_str="1",
                    )
                )
            elif response.http_status == 404:
                raise ItemNotFound
            else:
                raise UnexpectedAddonError

    def _parse_github_item_id(self, item_id: str) -> tuple[str, str, str]:
        try:
            owner_repo, path = item_id.split(":", maxsplit=1)
            owner, repo = owner_repo.split("/", maxsplit=1)
            return owner, repo, path
        except ValueError:
            raise ValueError(
                f"Invalid item_id format: {item_id}. Expected 'owner/repo:path'"
            )

    def _parse_github_item(self, item_json: dict, full_name: str) -> storage.ItemResult:
        item_type = (
            ItemType.FILE if item_json.get("type") == "file" else ItemType.FOLDER
        )
        item_name = item_json["name"]
        if item_json.get("type") == "dir":
            item_id = full_name + item_name
        else:
            item_id = item_json["path"]
        return storage.ItemResult(
            item_id=item_id,
            item_name=item_name,
            item_type=item_type,
            may_contain_root_candidates=False,
            can_be_root=False,
        )

    def _parse_github_repo(self, repo_json: dict) -> storage.ItemResult:
        return storage.ItemResult(
            item_id=repo_json["full_name"] + ":",
            item_name=repo_json["name"],
            item_type=ItemType.FOLDER,
            may_contain_root_candidates=False,
        )
