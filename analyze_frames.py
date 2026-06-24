#!/usr/bin/env python3
"""
在 .venv (Python 3.11) 中运行 Qwen-VL 帧分析
输入: 帧目录路径、API Key、帧间隔
输出: JSON 列表 [{"timestamp": N, "description": "..."}]

由 harvest.py 通过 subprocess 调用，不要直接运行。
"""

import base64
import json
import sys
import time
from pathlib import Path


def analyze_frames(frames_dir: str, api_key: str, interval: int) -> list[dict]:
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    frames_path = Path(frames_dir)
    frames = sorted(frames_path.glob("frame_*.jpg"))

    results = []
    for i, frame_path in enumerate(frames):
        ts = i * interval

        with open(frame_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        try:
            resp = client.chat.completions.create(
                model="qwen-vl-plus",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "用中文描述这个视频画面（不超过3句话）。重点关注：\n"
                                "1) 屏幕/白板/幻灯片上有什么内容（代码、公式、图表、文字）\n"
                                "2) 人物在做什么动作\n"
                                "3) 画面中出现的关键文字或标题"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                        },
                    ],
                }],
                max_tokens=200,
            )
            desc = resp.choices[0].message.content.strip()
        except Exception as e:
            desc = f"[分析失败: {e}]"

        results.append({"timestamp": ts, "description": desc})
        sys.stderr.buffer.write(f"  [{ts}s] {desc[:50]}...\n".encode("utf-8"))
        time.sleep(0.5)

    return results


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python analyze_frames.py <frames_dir> <api_key> <interval>")
        sys.exit(1)

    frames_dir = sys.argv[1]
    api_key = sys.argv[2]
    interval = int(sys.argv[3])

    results = analyze_frames(frames_dir, api_key, interval)
    sys.stdout.buffer.write(json.dumps(results, ensure_ascii=False).encode("utf-8"))
