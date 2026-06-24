---
name: harvester
description: |
  收割机 · 抖音博主内容采集 + 多模态蒸馏。
  输入博主主页 URL，自动下载视频、转录语音、用视觉模型分析关键帧，输出结构化 markdown 蒸馏报告。
  触发词：「收割」「采集」「harvest」「蒸馏XX的视频」「下载XX的内容」「爬XX的抖音」
---

# 收割机 · Harvester

> 输入一个抖音博主的主页链接，自动完成：视频下载 → 语音转录 → 画面理解 → 知识蒸馏

---

## 工作流程

```
博主主页 URL
  │
  ├─→ Douyin API 获取视频列表（get_videos.py，Python 3.11）
  │
  ├─→ 直链下载视频（urllib）
  │
  ├─→ Whisper 转录语音（带时间戳）
  │
  ├─→ ffmpeg 按间隔提取关键帧
  │
  ├─→ Qwen-VL 分析每帧画面（analyze_frames.py，Python 3.11）
  │
  └─→ 输出多模态时间线 + 完整文字稿（distilled.md）
```

---

## 安装

### 1. 命令行工具

```powershell
winget install yt-dlp
winget install ffmpeg
```

### 2. Python 依赖

```bash
pip install openai-whisper openai

# 建 Python 3.11 虚拟环境（用于 Douyin API 和 Qwen-VL）
uv venv .venv --python 3.11
uv pip install openai requests --python .venv/Scripts/python.exe
```

### 3. 提取抖音 Cookie（一次性，需管理员权限）

```powershell
# 用管理员 PowerShell 运行
python extract_cookie.py
```

自动从 Edge/Chrome 读取已登录的抖音 Cookie，保存到 `douyin_cookie.txt`。Cookie 失效后重新运行即可。

### 4. 视觉分析 API Key

申请阿里百炼 API Key：https://bailian.console.aliyun.com/

---

## 使用

```powershell
# 采集博主主页，完整多模态分析
python harvest.py "https://www.douyin.com/user/xxx" --max 5 --api-key sk-xxx

# 只要文字稿，不用 API Key
python harvest.py "https://www.douyin.com/user/xxx" --max 10 --skip-visual

# 常用参数
python harvest.py "URL" \
  --max 10 \
  --whisper-model small \    # tiny(快) / small / medium(中文最准) / large
  --frame-interval 20 \      # 每20秒取一帧，短视频可改为10
  --output my_output \       # 自定义输出目录
  --api-key sk-xxx
```

---

## 输出结构

```
harvest_output/
└── {视频ID}/
    ├── distilled.md        # ★ 多模态蒸馏报告（画面+语音时间线）
    ├── transcript.json     # Whisper 原始转录
    └── frames/             # 关键帧图片
```

### distilled.md 示例

```markdown
## 多模态时间线

**[0s]** 画面：一位女性站在现代化建筑前，面向镜头说话，穿黑色上衣佩戴金色项链。
> 语音：今天我来讲讲 AI 时代的焦虑问题...

**[30s]** 画面：屏幕字幕显示「让我们的工作节奏都在变快」，人物表情认真。
> 语音：AI 发展非常快，特别是过年以来迭代速度...
```

---

## 文件说明

| 文件 | 作用 |
|------|------|
| `harvest.py` | 主脚本，协调全流程 |
| `extract_cookie.py` | 从 Edge/Chrome 提取抖音 Cookie（需管理员） |
| `get_videos.py` | 调用 Douyin API 获取博主视频列表 |
| `analyze_frames.py` | 调用 Qwen-VL 分析视频关键帧 |

---

## 注意事项

- Cookie 有效期通常几周，失效后重新运行 `extract_cookie.py`
- Qwen-VL-Plus 费用约 ¥0.02-0.05/条短视频
- Whisper `medium` 模型中文识别最准，首次运行需下载约 1.4GB
- 仅供个人学习研究使用

---

MIT · 2026
