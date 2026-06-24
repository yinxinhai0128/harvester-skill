#!/usr/bin/env python3
"""
从 Edge/Chrome 自动提取抖音 Cookie，保存到 douyin_cookie.txt
需要管理员权限运行（Edge v130+ 使用应用级加密）

用法（管理员 PowerShell）:
  cd C:/Users/LENOVO/harvester-skill
  python extract_cookie.py
"""

import sys
from pathlib import Path

OUTPUT_FILE = Path("douyin_cookie.txt")

KEY_COOKIES = ["sessionid", "passport_auth_status", "LOGIN_STATUS", "uid_tt", "ttwid"]


def try_rookiepy(browser: str) -> dict:
    try:
        import rookiepy
        fn = getattr(rookiepy, browser, None)
        if fn is None:
            return {}
        cookies = fn(["douyin.com"])
        return {c["name"]: c["value"] for c in cookies}
    except RuntimeError as e:
        if "admin" in str(e).lower():
            raise
        return {}
    except Exception:
        return {}


def main():
    print("正在提取抖音 Cookie（需要管理员权限）...\n")

    cookies = {}

    # 优先尝试 Edge，再尝试 Chrome
    for browser in ("edge", "chrome"):
        print(f"  尝试 {browser}...")
        try:
            cookies = try_rookiepy(browser)
            if cookies:
                print(f"  [OK] 从 {browser} 提取到 {len(cookies)} 个抖音 Cookie")
                break
        except RuntimeError:
            print(f"  [需要管理员权限] 请用管理员 PowerShell 重新运行此脚本")
            sys.exit(1)

    if not cookies:
        print("\n[失败] 未找到抖音 Cookie。可能原因：")
        print("  1. 浏览器中未登录 douyin.com")
        print("  2. Cookie 已过期（重新在浏览器中登录抖音后再运行）")
        print("  3. 使用了与 Chrome/Edge 不同的浏览器")
        sys.exit(1)

    # 检查关键登录 Cookie
    found_keys = [k for k in KEY_COOKIES if k in cookies]
    if not found_keys:
        print("\n[警告] 未检测到登录态 Cookie，请先在浏览器中登录抖音后重试")
        sys.exit(1)

    print(f"  登录态确认: {', '.join(found_keys)}")

    # 保存
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    OUTPUT_FILE.write_text(cookie_str, encoding="utf-8")

    print(f"\n[完成] Cookie 已保存到 {OUTPUT_FILE.resolve()}")
    print("下一步：python harvest.py <用户主页URL>")


if __name__ == "__main__":
    main()
