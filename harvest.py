#!/usr/bin/env python3
"""
harvest.py — 抖音博主内容采集 + 多模态蒸馏
用法: python harvest.py <URL> [选项]

示例:
  python harvest.py "https://www.douyin.com/user/xxx" --max 3
  python harvest.py "https://www.douyin.com/video/xxx"  # 单条测试
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# ── 环境检查 ──────────────────────────────────────────────────────────────────

def check_deps():
    missing_cmds = [cmd for cmd in ("yt-dlp", "ffmpeg", "ffprobe") if not shutil.which(cmd)]
    if missing_cmds:
        print(f"[错误] 缺少命令行工具: {', '.join(missing_cmds)}")
        print("  安装: winget install yt-dlp; winget install ffmpeg")
        sys.exit(1)

    for pkg, pip_name in [("whisper", "openai-whisper"), ("openai", "openai")]:
        try:
            __import__(pkg)
        except ImportError:
            print(f"[错误] 缺少 Python 包: pip install {pip_name}")
            sys.exit(1)

    print("[检查] 依赖全部就绪")


# ── Cookie 工具 ───────────────────────────────────────────────────────────────

COOKIE_FILE = Path(__file__).parent / "douyin_cookie.txt"

def load_cookie_str() -> str:
    if not COOKIE_FILE.exists():
        print("[错误] 未找到 douyin_cookie.txt，请先运行：python extract_cookie.py（需管理员）")
        sys.exit(1)
    return COOKIE_FILE.read_text(encoding="utf-8").strip()


def write_netscape_cookies(cookie_str: str, out_path: Path):
    """把 key=value; key=value 格式转为 yt-dlp 认识的 Netscape 格式"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for pair in cookie_str.split("; "):
            if "=" not in pair:
                continue
            name, value = pair.split("=", 1)
            f.write(f".douyin.com\tTRUE\t/\tFALSE\t9999999999\t{name.strip()}\t{value.strip()}\n")


# ── 下载 ──────────────────────────────────────────────────────────────────────

def download_videos(url: str, out_dir: Path, max_count: int) -> list[Path]:
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    cookie_str = load_cookie_str()

    if "/user/" in url:
        return _download_profile(url, raw_dir, max_count, cookie_str)
    else:
        return _download_single_ytdlp(url, raw_dir, max_count, cookie_str)


def _download_profile(url: str, raw_dir: Path, max_count: int, cookie_str: str) -> list[Path]:
    """从抖音 API 获取视频列表，再用 yt-dlp 逐条下载"""
    import re

    # 从 URL 提取 sec_uid
    m = re.search(r"/user/([^/?]+)", url)
    if not m:
        print("[错误] 无法从 URL 提取用户 ID，请确认是博主主页链接")
        sys.exit(1)
    sec_uid = m.group(1)

    # 用 3.11 venv 调 Douyin API 获取视频列表
    venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    get_videos_script = Path(__file__).parent / "get_videos.py"

    print(f"\n[获取列表] 查询博主视频列表（最多 {max_count} 条）...")
    result = subprocess.run(
        [str(venv_python), str(get_videos_script), sec_uid, str(max_count)],
        capture_output=True, text=True, cwd=Path(__file__).parent,
    )

    if result.returncode != 0 or not result.stdout.strip():
        print(f"[错误] 获取视频列表失败: {result.stderr[:200]}")
        sys.exit(1)

    try:
        video_list = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"[错误] API 返回格式异常: {result.stdout[:200]}")
        sys.exit(1)

    if not video_list:
        print("[错误] API 返回 0 条视频，可能 Cookie 已失效，请重新运行 extract_cookie.py")
        sys.exit(1)

    print(f"[获取列表] 找到 {len(video_list)} 条视频")

    # 写 Netscape 格式 cookie 供 yt-dlp 使用
    netscape_file = raw_dir / "_cookies.txt"
    write_netscape_cookies(cookie_str, netscape_file)

    # 逐条下载（直链 + requests，绕过 yt-dlp Cookie 检查）
    import urllib.request

    headers_dl = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Referer": "https://www.douyin.com/",
        "Cookie": cookie_str,
    }

    for i, video in enumerate(video_list):
        vid_id = video["id"]
        title = video["title"][:40].strip() or vid_id
        dl_url = video.get("download_url", "")
        out_path = raw_dir / f"{vid_id}.mp4"

        print(f"  [{i+1}/{len(video_list)}] {title}")

        if not dl_url:
            print(f"    [跳过] 无直链")
            continue

        if out_path.exists():
            print(f"    [跳过] 已存在")
            continue

        success = False
        try:
            req = urllib.request.Request(dl_url, headers=headers_dl)
            with urllib.request.urlopen(req, timeout=60) as resp, open(out_path, "wb") as f:
                downloaded_bytes = 0
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded_bytes += len(chunk)
            success = True
            print(f"    [OK] {downloaded_bytes // 1024 // 1024} MB")
        except Exception as e:
            print(f"    [失败] {e}")
            if not success:
                out_path.unlink(missing_ok=True)

        if i < len(video_list) - 1:
            time.sleep(2)

    videos = sorted(raw_dir.glob("*.mp4"))
    print(f"[下载完成] {len(videos)} 个视频")
    return videos


def _download_single_ytdlp(url: str, raw_dir: Path, max_count: int, cookie_str: str) -> list[Path]:
    """用 yt-dlp 下载单条或短视频链接"""
    netscape_file = raw_dir / "_cookies.txt"
    write_netscape_cookies(cookie_str, netscape_file)

    print(f"\n[下载] 单视频模式（yt-dlp），最多 {max_count} 条...")
    cmd = [
        "yt-dlp",
        "--playlist-end", str(max_count),
        "-o", str(raw_dir / "%(id)s_%(title).50s.%(ext)s"),
        "--write-info-json",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "--merge-output-format", "mp4",
        "--cookies", str(netscape_file),
        "--no-warnings",
        "--retries", "3",
        url,
    ]
    subprocess.run(cmd)
    netscape_file.unlink(missing_ok=True)

    videos = sorted(raw_dir.glob("*.mp4"))
    print(f"[下载完成] {len(videos)} 个视频")
    return videos


# ── 转录 ──────────────────────────────────────────────────────────────────────

def transcribe(video_path: Path, model) -> dict:
    print(f"  -> 转录中...")
    result = model.transcribe(str(video_path), language="zh")
    segments = [
        {
            "start": round(s["start"], 1),
            "end": round(s["end"], 1),
            "text": s["text"].strip(),
        }
        for s in result["segments"]
        if s["text"].strip()
    ]
    return {"full_text": result["text"].strip(), "segments": segments}


# ── 关键帧提取 ────────────────────────────────────────────────────────────────

def extract_keyframes(video_path: Path, frames_dir: Path, interval: int) -> list[tuple[int, Path]]:
    frames_dir.mkdir(parents=True, exist_ok=True)

    # 获取视频时长
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video_path)],
        capture_output=True, text=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])

    # 按固定间隔抽帧
    subprocess.run(
        [
            "ffmpeg", "-i", str(video_path),
            "-vf", f"fps=1/{interval}",
            "-q:v", "3",
            str(frames_dir / "frame_%04d.jpg"),
            "-y", "-loglevel", "error",
        ],
        check=True,
    )

    frames = sorted(frames_dir.glob("frame_*.jpg"))
    timestamped = [(i * interval, f) for i, f in enumerate(frames)]
    print(f"  -> 提取 {len(frames)} 帧（时长 {int(duration)}s，每 {interval}s 一帧）")
    return timestamped


# ── 视觉分析 ──────────────────────────────────────────────────────────────────

def analyze_frames_batch(frames_dir: Path, api_key: str, interval: int) -> list[tuple[int, str]]:
    """调用 .venv Python 3.11 运行 analyze_frames.py，绕过 Python 3.9 的代理 SSL 问题"""
    venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    script = Path(__file__).parent / "analyze_frames.py"

    result = subprocess.run(
        [str(venv_python), str(script), str(frames_dir), api_key, str(interval)],
        capture_output=True,
    )

    stderr_text = result.stderr.decode("utf-8", errors="replace")
    stdout_text = result.stdout.decode("utf-8", errors="replace")

    if stderr_text.strip():
        print(stderr_text, end="")

    if not stdout_text.strip():
        print("  [警告] 视觉分析无输出，跳过")
        return []

    try:
        data = json.loads(stdout_text)
        return [(item["timestamp"], item["description"]) for item in data]
    except json.JSONDecodeError:
        print(f"  [警告] 视觉分析输出解析失败: {stdout_text[:100]}")
        return []


# ── 生成 Markdown ─────────────────────────────────────────────────────────────

def build_markdown(title: str, transcript: dict, frame_analysis: list[tuple[int, str]], interval: int) -> str:
    lines = [
        f"# {title}",
        f"*蒸馏时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## 多模态时间线",
        "",
    ]

    segs = transcript["segments"]
    seg_ptr = 0

    for ts, desc in frame_analysis:
        lines.append(f"**[{ts}s]** 画面：{desc}")

        # 找这段时间内的语音
        spoken = []
        while seg_ptr < len(segs) and segs[seg_ptr]["start"] < ts + interval:
            if segs[seg_ptr]["start"] >= ts:
                spoken.append(segs[seg_ptr]["text"])
            seg_ptr += 1

        if spoken:
            lines.append(f"> 语音：{''.join(spoken)}")
        lines.append("")

    lines += [
        "---",
        "",
        "## 完整文字稿",
        "",
        transcript["full_text"],
    ]

    return "\n".join(lines)


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="抖音内容采集 + 多模态蒸馏")
    parser.add_argument("url", help="抖音博主主页 URL 或单个视频 URL")
    parser.add_argument("--max", type=int, default=3, metavar="N",
                        help="最多处理几条视频（默认 3）")
    parser.add_argument("--api-key", default=os.getenv("DASHSCOPE_API_KEY"),
                        help="阿里百炼 API Key（也可设置环境变量 DASHSCOPE_API_KEY）")
    parser.add_argument("--output", default="harvest_output", help="输出目录（默认 harvest_output）")
    parser.add_argument("--whisper-model", default="medium",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 模型（默认 medium，中文效果好；tiny 最快但准确率低）")
    parser.add_argument("--frame-interval", type=int, default=30,
                        help="每多少秒提取一帧（默认 30，短视频可改为 10）")
    parser.add_argument("--skip-visual", action="store_true",
                        help="跳过视觉分析，只输出文字稿（无需 API Key）")
    args = parser.parse_args()

    if not args.skip_visual and not args.api_key:
        print("[错误] 需要阿里百炼 API Key")
        print("  方式 1: python harvest.py ... --api-key sk-xxx")
        print("  方式 2: 设置环境变量 set DASHSCOPE_API_KEY=sk-xxx")
        print("  方式 3: 只要文字稿可以加 --skip-visual 跳过视觉分析")
        sys.exit(1)

    check_deps()

    import whisper

    out_dir = Path(args.output)
    out_dir.mkdir(exist_ok=True)

    # 加载模型（放在下载之前，确保环境 OK 再开始下载）
    print(f"[准备] 加载 whisper-{args.whisper_model}（首次运行会下载模型，需要几分钟）...")
    whisper_model = whisper.load_model(args.whisper_model)
    print("[准备] Whisper 就绪")


    # ── Phase 1: 下载 ──
    videos = download_videos(args.url, out_dir, args.max)
    if not videos:
        print("[错误] 没有下载到视频，请检查 URL 和 Cookie")
        sys.exit(1)

    # ── Phase 2-4: 逐条处理 ──
    for i, video in enumerate(videos):
        print(f"\n== 第 {i+1}/{len(videos)} 条: {video.name} ==")

        work_dir = out_dir / video.stem
        work_dir.mkdir(exist_ok=True)

        # 转录
        transcript = transcribe(video, whisper_model)
        (work_dir / "transcript.json").write_text(
            json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 关键帧 + 视觉分析
        frame_analysis = []
        if not args.skip_visual:
            frames_dir = work_dir / "frames"
            extract_keyframes(video, frames_dir, args.frame_interval)
            print(f"  -> 调用 Qwen-VL 分析帧...")
            frame_analysis = analyze_frames_batch(frames_dir, args.api_key, args.frame_interval)
        else:
            print("  -> 跳过视觉分析（--skip-visual）")

        # 生成 Markdown
        md_content = build_markdown(video.stem, transcript, frame_analysis, args.frame_interval)
        md_path = work_dir / "distilled.md"
        md_path.write_text(md_content, encoding="utf-8")
        print(f"  [OK] 输出 -> {md_path}")

        if i < len(videos) - 1:
            time.sleep(3)

    print(f"\n[全部完成] 输出目录: {out_dir.resolve()}")
    print(f"  蒸馏报告: {out_dir.resolve()}\\*\\distilled.md")


if __name__ == "__main__":
    main()
