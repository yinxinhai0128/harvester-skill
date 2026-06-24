#!/usr/bin/env python3
"""
从抖音 API 获取博主视频列表，返回视频 ID 列表
供 harvest.py 调用（需在 .venv Python 3.11 环境下运行）
"""

import json
import sys
import time
import requests
from pathlib import Path


def get_video_list(sec_uid: str, cookie_str: str, max_count: int = 10) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Referer": "https://www.douyin.com/",
        "Cookie": cookie_str,
    }

    videos = []
    cursor = 0

    while len(videos) < max_count:
        params = {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "sec_user_id": sec_uid,
            "count": "20",
            "max_cursor": str(cursor),
            "cookie_enabled": "true",
            "platform": "PC",
        }

        try:
            resp = requests.get(
                "https://www.douyin.com/aweme/v1/web/aweme/post/",
                headers=headers,
                params=params,
                timeout=15,
            )
            data = resp.json()
        except Exception as e:
            print(f"[API 错误] {e}", file=sys.stderr)
            break

        aweme_list = data.get("aweme_list") or []
        for item in aweme_list:
            # 提取直链：优先无水印，其次普通链接
            download_url = ""
            video_info = item.get("video", {})
            # 无水印链接
            play_addr = video_info.get("play_addr_h264") or video_info.get("play_addr") or {}
            url_list = play_addr.get("url_list", [])
            if url_list:
                download_url = url_list[0]

            videos.append({
                "id": item["aweme_id"],
                "title": item.get("desc", "")[:60],
                "download_url": download_url,
            })
            if len(videos) >= max_count:
                break

        if not data.get("has_more") or not aweme_list:
            break

        cursor = data.get("max_cursor", 0)
        time.sleep(1)

    return videos


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python get_videos.py <sec_uid> <max_count>")
        sys.exit(1)

    sec_uid = sys.argv[1]
    max_count = int(sys.argv[2])
    cookie_str = Path("douyin_cookie.txt").read_text(encoding="utf-8").strip()

    videos = get_video_list(sec_uid, cookie_str, max_count)
    print(json.dumps(videos, ensure_ascii=False))
