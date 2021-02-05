from typing import Optional, TypedDict


class Volume(TypedDict):
    name: str
    local_folder: str
    mount: str


class Permissions(TypedDict):
    folder: str
    user: str
    group: Optional[str]
    mode: Optional[str]
