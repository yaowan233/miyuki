import httpx
from .models import NewScore


# 设置请求头
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "X-CSRF-Token": "IpTTWLDOLQ4j6pILBFp2hFYludvukO9oPR3CJ57t",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://osu.ppy.sh/beatmapsets/2205747",
    "Cookie": "XSRF-TOKEN=IpTTWLDOLQ4j6pILBFp2hFYludvukO9oPR3CJ57t; osu_session=eyJpdiI6Ik1WSHQ5RTFMYnlITmpncmxJUjJXY1E9PSIsInZhbHVlIjoiSXF3T1FVeXlNbkV3SitEaWVxRTJIaWp5RFIxZlYyekNuVC9tMzFMbXQ0bVFwUUExeTNxUC9SOW9VU3ZVWkFFRHRtMmlBL0ppVmVNSXlPVnpHZUVCbTZ2QklkNSt0cG1mUkM0bGRRNFNLOXlJWWRrSmRreUFSZEtOOUY3UnlleGhsNndkdmh4QXp2bVpvRzVUaEVVQ0l3PT0iLCJtYWMiOiIyZmNlYjU3MjVjN2MwM2JkNjhjMzU3MmYzZmFiNWMwMjUyZjczYzEwMGMzYjVjYmM3MWZiMjVhYmJjYjYxYmU0IiwidGFnIjoiIn0%3D; cf_clearance=RraFdZDeipbhbF5CCpkhokL9ItqOI.Pi2f0bT13W1x8-1708665910-1.0-AXSMZz+fqZeEYm2W5rp/mIK8/Vvx7vOKavSQ+oPHgI/iD8WyCYIHSeJIGAmXgsJ8Z8tR3r5MbQZ5GLRGobDwUx0=; locale=zh",
}


# 发送 GET 请求
async def fetch_scores(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return [NewScore.parse_obj(i) for i in response.json()['scores']]  # 返回 JSON 数据


async def get_score_list(map_id: int, mode: str, mods: list[str], is_country: bool):
    url = f"https://osu.ppy.sh/beatmaps/{map_id}/scores?mode={mode}"
    if mods:
        for i in mods:
            url += f"&mods[]={i}"
    if is_country:
        url += "&type=country"
    data = await fetch_scores(url)
    return data

