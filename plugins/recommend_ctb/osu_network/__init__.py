from enum import Enum
from pathlib import Path
from httpx import AsyncClient, Response, NetworkError
from typing import Union, Optional
from expiringdict import ExpiringDict
from ..models import Beatmap, NewScore
from loguru import logger
from ..network import auto_retry, get_first_response


api = "https://osu.ppy.sh/api/v2"
key = "wCbkMYjnW0GCjdc6Dw7e11M7KpIOHBi9b8xOyAKx"
client_id = 28516
cache = ExpiringDict(max_len=1, max_age_seconds=86400)
proxy = None
map_path = Path() / "data" / "osu" / "map"
map_path.mkdir(parents=True, exist_ok=True)


class TokenExpireError(NetworkError):
    pass


class OsuGameMode(Enum):
    osu = "osu"
    taiko = "taiko"
    ctb = "fruits"
    mania = "mania"


async def renew_token():
    url = "https://osu.ppy.sh/oauth/token"
    async with AsyncClient(timeout=100) as client:
        client: AsyncClient
        req = await client.post(
            url,
            json={
                "client_id": f"{client_id}",
                "client_secret": f"{key}",
                "grant_type": "client_credentials",
                "scope": "public",
            },
        )
    if req.status_code == 200:
        osu_token = req.json()
        cache.update({"token": osu_token["access_token"]})
    else:
        logger.error(f"更新OSU token出错 错误{req.status_code}")


async def get_header():
    token = cache.get("token")
    if not token:
        await renew_token()
        token = cache.get("token")
    return {"Authorization": f"Bearer {token}", "x-api-version": "20220705"}


@auto_retry
async def safe_async_get(
    url, headers: Optional[dict] = None, params: Optional[dict] = None
) -> Response:
    async with AsyncClient(timeout=100, proxy=proxy, follow_redirects=True) as client:
        client: AsyncClient
        req = await client.get(url, headers=headers, params=params)
    return req


@auto_retry
async def safe_async_post(url, headers=None, data=None, json=None) -> Response:
    async with AsyncClient(timeout=100, proxy=proxy) as client:
        client: AsyncClient
        req = await client.post(url, headers=headers, data=data, json=json)
    return req


async def osu_api(
    project: str,
    uid: int = 0,
    mode: str = "osu",
    map_id: int = 0,
    is_name: bool = False,
    offset: int = 0,
    limit: int = 5,
) -> Union[str, dict]:
    if is_name:
        info = await get_user_info(f"{api}/users/{uid}/{mode}?key=username")
        if isinstance(info, str):
            return info
        else:
            uid = info["id"]
    if project == "info" or project == "bind" or project == "update":
        url = f"{api}/users/{uid}/{mode}"
    elif project == "recent":
        url = f"{api}/users/{uid}/scores/recent?mode={mode}&include_fails=1&limit={limit}&offset={offset}"
    elif project == "pr":
        url = (
            f"{api}/users/{uid}/scores/recent?mode={mode}&limit={limit}&offset={offset}"
        )
    elif project == "score":
        url = f"{api}/beatmaps/{map_id}/scores/users/{uid}/all?mode={mode}"
    elif project == "bp":
        url = f"{api}/users/{uid}/scores/best?mode={mode}&limit=100"
    elif project == "map":
        url = f"{api}/beatmaps/{map_id}"
    else:
        raise "Project Error"
    return await api_info(project, url)


async def get_user_info(url: str) -> Union[dict, str]:
    header = await get_header()
    req = await safe_async_get(url, headers=header)
    if not req:
        return "api请求失败，请稍后再试"
    elif req.status_code == 404:
        return "未找到该玩家，请确认玩家ID是否正确，有无多余或缺少的空格"
    elif req.status_code == 200:
        return req.json()
    else:
        return "API请求失败，请联系管理员"


async def api_info(project: str, url: str) -> Union[dict, str]:
    if project == "mapinfo" or project == "PPCalc":
        header = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) Chrome/78.0.3904.108"
        }
    else:
        header = await get_header()
    req = await safe_async_get(url, headers=header)
    if not req:
        return "api请求失败，请稍后再试"
    if req.status_code >= 400:
        if project == "info" or project == "bind":
            return "未找到该玩家，请确认玩家ID"
        elif project == "recent":
            return "未找到该玩家，请确认玩家ID"
        elif project == "score":
            return "未找到该地图成绩，请检查是否搞混了mapID与setID或模式"
        elif project == "bp":
            return "未找到该玩家BP"
        elif project == "map":
            return "未找到该地图，请检查是否搞混了mapID与setID"
        else:
            return "API请求失败，请联系管理员或稍后再尝试"
    return req.json()


def calc_songlen(length: int) -> str:
    map_len = list(divmod(int(length), 60))
    map_len[1] = map_len[1] if map_len[1] >= 10 else f"0{map_len[1]}"
    music_len = f"{map_len[0]}:{map_len[1]}"
    return music_len


@auto_retry
async def download_osu(map_id):
    url = [f"https://osu.ppy.sh/osu/{map_id}", f"https://api.osu.direct/osu/{map_id}"]
    logger.info(f"开始下载谱面: <{map_id}>")
    if req := await get_first_response(url):
        filename = f"{map_id}.osu"
        filepath = map_path / filename
        with open(filepath, "wb") as f:
            f.write(req)
        return filepath
    else:
        raise NetworkError(f"下载 map_id {map_id} 出错，请稍后再试")


async def get_map_info(map_id) -> Beatmap:
    url = f"{api}/beatmaps/{map_id}"
    header = await get_header()
    req = await safe_async_get(url, headers=header)
    if not req or req.status_code >= 400:
        raise NetworkError(f"获取地图信息 {map_id} 时出错")
    return Beatmap(**req.json())


async def get_ranking(mode: str, page=1):
    url = f"{api}/rankings/{mode}/performance"
    header = await get_header()
    req = await safe_async_get(url, headers=header, params={"cursor[page]": page})
    if not req or req.status_code >= 400:
        raise NetworkError
    return [i['user']['id'] for i in req.json()['ranking']]


async def get_bplist(uid: int, mode: str):
    url = f"{api}/users/{uid}/scores/best?mode={mode}&limit=100"
    header = await get_header()
    req = await safe_async_get(url, headers=header)

    return [NewScore(**i) for i in req.json()]


