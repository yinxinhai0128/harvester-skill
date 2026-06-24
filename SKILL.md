---
name: harvester
description: |
  收割机 · 全平台创作者内容采集+多模态解析+蒸馏。
  输入一个作者名，自动识别平台→采集视频/文章/社交帖子→多模态解析（视频不只字幕，含关键帧视觉理解）→蒸馏输出结构化知识。
  支持 YouTube/B站/抖音/公众号/X/小红书/知乎/通用网页。
  触发词：「收割」「采集作者」「harvest」「下载XX的所有内容」「蒸馏XX」「爬XX的视频」「多模态解析」
---

# 收割机 · Harvester

> 「字幕只是视频 20% 的信息。我要的是他在说什么的同时做了什么。」
>
> 输入一个创作者的名字。收割机自动识别他在哪些平台、采集所有内容、用多模态管线解析视频、蒸馏出结构化知识。

---

## 核心理念

### 为什么纯字幕不够

一个典型的抖音技术视频包含：

| 信息层 | 占比 | 纯字幕能捕获？ |
|--------|------|--------------|
| 语音内容 | 30% | ✅ 能 |
| 屏幕演示（代码/图表/操作） | 35% | ❌ 不能 |
| 表情与肢体语言 | 10% | ❌ 不能 |
| 画面切换与节奏 | 10% | ❌ 不能 |
| 文字叠加与标注 | 15% | ❌ 不能 |

**结论**：纯字幕丢掉 70% 的信息。收割机用多模态管线补回来。

### 多模态视频解析管线

```
视频文件
  │
  ├─→ ffmpeg 提取音频 ──→ whisper 转录 ──→ 带时间戳文字稿
  │
  ├─→ PySceneDetect 场景检测 ──→ 提取关键帧（每 5-30s 一帧）
  │     │
  │     └─→ Gemini Vision / Qwen-VL 分析每帧
  │           ├─ 画面内容：「老师在终端里运行了 pip install xxx」
  │           ├─ 文字标注：「幻灯片标题是『为什么 RLHF 不稳定』」
  │           └─ 动作识别：「老师用鼠标指向了 loss 曲线的最低点」
  │
  └─→ 时间轴对齐 + LLM 融合
        └─→ 输出：「03:15 — 老师打开终端演示 pip install 的同时，
              解释了依赖管理的重要性」
```

---

## 平台路由表

🔴 **CHECKPOINT** — 收到作者名后，先用此表确定去哪些平台。不要假设作者只在某个平台。

| 平台 | 识别方式 | 下载工具 | 内容类型 | 解析方式 |
|------|---------|---------|---------|---------|
| YouTube | 搜索 `@用户名` | yt-dlp | 长视频 | 多模态管线 |
| B站 | 搜索 UID/空间 | yt-dlp + bilibili-api | 长视频 | 多模态管线 |
| 抖音 | 搜索用户名 | douyin-downloader | 短视频 | 多模态管线 |
| 公众号 | 搜索公众号名 | wechat-article-downloader | 长文章 | trafilatura 清洗 |
| X/Twitter | 搜索 @handle | twikit | 短推文 | 结构化提取 |
| 小红书 | 搜索用户名 | xiaohongshu-crawler | 图文笔记 | trafilatura + 图片 |
| 知乎 | 搜索用户名 | trafilatura | 长回答 | 正文提取 |
| 通用博客 | 用户提供 URL | trafilatura | 文章 | 正文提取 |

**优先级**：有视频的平台优先（视频信息密度 > 文章 > 社交帖子）。

---

## 工作流

### Phase 0：确认目标

收到作者名后，通过 web_search 确认：

1. **作者全平台身份** — 在哪些平台有账号？每个平台的 ID/用户名是什么？
2. **采集范围** — 全部内容？最近 N 条？特定主题？
3. **采集深度** — 只采集元数据？完整下载？多模态解析？
4. **输出用途** — 个人存档？蒸馏分析？训练数据？

🔴 **CHECKPOINT** — 输出「平台覆盖清单」让用户确认：

```
确认采集范围：
  YouTube: @alchain — 约 20 条视频
  B站: 花叔 — 约 50 条视频
  公众号: 花叔 — 约 100 篇文章
  X: @AlchainHust — 约 500 条推文

预计数据量：视频 ~2GB，文章 ~50MB，推文 ~5MB
预计耗时：视频多模态解析最慢，约 2-5 分钟/条
```

### Phase 1：环境检查

在采集前检查工具链：

```bash
# 必须
which yt-dlp ffmpeg python3

# 视频多模态
python3 -c "import whisper" 2>/dev/null && echo "whisper: OK" || echo "whisper: 需安装"
python3 -c "from scenedetect import detect" 2>/dev/null && echo "PySceneDetect: OK" || echo "PySceneDetect: 需安装"

# 视觉理解（至少安装一个）
echo "$GEMINI_API_KEY" > /dev/null && echo "Gemini: OK"
python3 -c "from openai import OpenAI" 2>/dev/null && echo "OpenAI Vision: OK"
```

**如果缺少工具**：自动尝试 `pip install`。如果安装失败 → 告知用户缺什么 + 降级方案。

**降级方案**：
- 没有 PySceneDetect → 每 30 秒均匀抽帧（质量下降但能跑）
- 没有 Gemini API Key → 用 GPT-4o Vision 或本地 Qwen-VL
- 都没有 → 退回纯字幕模式，标注「多模态不可用，信息完整性 ~30%」

### Phase 2：采集

按平台并行启动采集。每个平台一个独立任务。

**通用采集脚本模板**：

```python
# 抖音采集示例
# 参考教程 Day06 的 Cookie 管理和反爬策略
import subprocess, time, random

def download_douyin_profile(username, output_dir):
    # 1. 先获取用户所有视频 ID
    # 2. 逐个下载（加随机延迟 2-5s，教程 Day09 代理 IP 策略）
    # 3. 保存元数据
    for i, video_id in enumerate(video_ids):
        time.sleep(random.uniform(2, 5))  # 反爬：随机延迟
        subprocess.run([
            "douyin-downloader", video_id,
            "--output", f"{output_dir}/{i:03d}_{video_id}.mp4"
        ])
```

**反爬策略（来自爬虫教程）**：

| 策略 | 适用平台 | 实现 |
|------|---------|------|
| User-Agent 伪装 | 所有 | 随机 UA 池 |
| Cookie 维持 | 抖音/B站/知乎 | Session 对象 |
| 请求间隔 | 所有 | random(2,8)秒 |
| 代理 IP | 公众号/小红书 | 代理池轮换 |
| Referer 校验 | B站/公众号 | 设置正确 Referer |

### Phase 3：多模态解析（核心）

对于每个采集到的视频，执行：

#### Step 3a：音频提取 + 转录

```bash
# 提取音频
ffmpeg -i video.mp4 -vn -acodec pcm_s16le audio.wav

# whisper 转录（带时间戳）
python3 -c "
import whisper
model = whisper.load_model('medium')  # 中文用 medium 或 large
result = model.transcribe('audio.wav', language='zh', word_timestamps=True)
# 输出每个词的时间戳
"
```

#### Step 3b：场景检测 + 关键帧提取

```bash
# PySceneDetect 检测场景切换
scenedetect -i video.mp4 detect-adaptive threshold 3.0 list-scenes

# 提取关键帧（每个场景中间位置取一帧）
ffmpeg -i video.mp4 -vf "select='eq(n,0)+if(gt(scene,0.3),1,0)'"   -vsync vfr frames/frame_%04d.png
```

**帧数控制**：短视频（<60s）约 5-15 帧；长视频（>10min）约 20-60 帧。

#### Step 3c：帧视觉分析

对每个关键帧调用视觉模型。**优先级**：Qwen-VL（国内性价比最高）→ DeepSeek-VL（最便宜）→ 本地部署。

**方案一：Qwen-VL（阿里百炼，推荐）**

国内最优选择。OpenAI 兼容 API，中文理解最好，¥0.0015/千tokens。

```bash
# 获取 API Key: https://bailian.console.aliyun.com/
export DASHSCOPE_API_KEY=sk-xxx
pip install openai  # Qwen-VL 使用 OpenAI 兼容接口
```

```python
from openai import OpenAI
import base64, os

client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

def analyze_frame_qwen(frame_path):
    with open(frame_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    response = client.chat.completions.create(
        model="qwen-vl-plus",  # 或 qwen-vl-max（更准但贵一倍）
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "描述这个视频画面的内容。重点："
                 "1)屏幕上有代码/图表/幻灯片/网页？2)文字标注或标题？"
                 "3)人物动作和表情？4)画面切换节奏？用中文回答，不超过3句话。"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ]
        }],
        max_tokens=300
    )
    return response.choices[0].message.content

# 批量分析
frame_descriptions = []
for fp in sorted(frame_paths):
    desc = analyze_frame_qwen(fp)
    frame_descriptions.append({"timestamp": extract_timestamp(fp), "description": desc})
```

**成本估算**：每条抖音短视频约 10 帧 → ¥0.02-0.05/条。分析 100 条视频约 ¥3-5。

**方案二：DeepSeek-VL2（最便宜）**

¥0.001/千tokens，比 Qwen-VL 还便宜。API 同样兼容 OpenAI 格式。

```python
client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)
# model="deepseek-vl2" — 调用方式同上
```

**方案三：本地部署（零成本，需 GPU）**

Qwen2.5-VL-7B-Instruct，8GB+ VRAM 即可。每帧零成本。

```bash
pip install transformers qwen-vl-utils torch
```

```python
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

model = Qwen2VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-7B-Instruct", torch_dtype="auto", device_map="auto"
)
processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-7B-Instruct")

# 分析单帧
messages = [{"role": "user", "content": [
    {"type": "image", "image": frame_path},
    {"type": "text", "text": "描述这个画面的内容，用中文，不超过3句话。"}
]}]
text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = processor(text=text, images=[...], return_tensors="pt").to(model.device)
output = model.generate(**inputs, max_new_tokens=300)
```

#### Step 3d：时间轴对齐 + 融合

将转录时间戳与帧时间戳对齐，生成完整的多模态时序描述：

```
[00:00-00:15] 片头 — 标题「为什么你的 RLHF 不 work」
[00:15-00:45] 老师口述 RLHF 的三个问题
  画面：幻灯片列出 3 点（reward hacking, mode collapse, KL divergence）
[00:45-02:10] 老师打开终端，演示 reward hacking 实例
  画面：VS Code 终端，运行 train.py 后 loss 不收敛
  ...
```

🔴 **CHECKPOINT** — 第一条视频解析完成后，展示样例给用户确认质量。确认后批量处理其余视频。

### Phase 4：蒸馏输出

所有内容采集+解析完成后，生成：

#### 4a：单条内容 markdown

每篇视频/文章一个 markdown 文件，包含多模态描述和关键论点。

#### 4b：全局蒸馏

跨所有内容，提取：

```
## {作者名} 全局蒸馏

### 核心论点（跨 ≥3 条内容复现）
- [论点1]：出现在视频 A(12:30)、文章 B(第3段)、推文 C
- [论点2]：...

### 方法论特征
- 表达风格：...
- 论证模式：...
- 常用技术栈：...

### 内容时间线
2026-01: 开始讲 XXX
2026-03: 转向 YYY
...

### 值得深入的方向
- 他在 ZZZ 上反复提到但没展开
- 他推荐的工具/资源汇总
```

---

## 反爬与伦理

### 必须遵守

1. **速率限制** — 每秒不超过 1 个请求，每个视频下载间隔 ≥ 3 秒
2. **Robots.txt** — 采集前检查目标网站的 robots.txt
3. **用户代理声明** — 使用诚实的 User-Agent
4. **不采集付费/私密内容** — 只采集公开可访问的内容
5. **个人使用** — 采集内容用于个人学习研究，不重新分发

### 教程来源的反爬知识点映射

| 教程 Day | 知识点 | 在本 skill 中的应用 |
|----------|--------|-------------------|
| Day01 | HTTP 请求格式 | 构造正确的 requests |
| Day05 | 编码处理 | 处理中文内容编码 |
| Day06 | Cookie/Session | 登录态维持 |
| Day07 | 正则表达式 | 从 HTML/JSON 提取数据 |
| Day08 | XPath | 解析网页结构 |
| Day09 | 代理 IP | 避免 IP 封禁 |

---

## 失败模式与 Fallback

| 场景 | 触发条件 | 处理 |
|------|---------|------|
| 视频下载失败 | yt-dlp 报错 (HTTP 403/地区限制) | 尝试 you-get 作为 fallback；仍失败 → 跳过该条，标注原因 |
| 抖音被限流 | 连续 3 个视频下载失败 | 等待 5 分钟 + 切换 User-Agent；仍失败 → 暂停抖音采集 |
| whisper 转录质量差 | 中文转录准确率 < 70% | 换用 larger 模型重新转录；如果环境不支持 → 使用 API (Groq Whisper) |
| 视觉模型不可用 | 所有 API 都挂了 | 退回纯字幕模式，标注「视觉分析不可用」。国内用户优先配 Qwen-VL（阿里百炼，¥0.0015/千tokens） |
| 关键帧太多 | 视频 > 1 小时 | 采样：每 60 秒取 1 帧 + 场景切换点 |
| 磁盘空间不足 | 下载目录 > 10GB | 暂停采集，告知用户；建议分批处理 |
| 作者不在平台上 | 搜索无结果 | 跳过该平台，标注「未找到」 |

---

## 输出结构

```
harvest_output/{作者名}/
├── videos/
│   ├── P01_视频标题/
│   │   ├── original.mp4           # 原始视频（可选）
│   │   ├── transcript.json        # whisper 转录 + 时间戳
│   │   ├── frames/                # 关键帧图片
│   │   │   ├── frame_001.png
│   │   │   └── frame_descriptions.json
│   │   └── multimodal.md          # ★ 多模态融合输出
│   └── P02_.../
├── articles/
│   ├── 文章标题.md                # 清洗后正文
│   └── meta.json
├── social/
│   ├── timeline.json              # 社交时间线
│   └── posts/{id}.json
├── summary.md                     # ★ 全局蒸馏报告
└── _harvest_log.json              # 采集日志
```

---

## 诚实边界

- **依赖外部工具** — yt-dlp、whisper、PySceneDetect 等需要预装。无法安装时功能降级
- **视觉模型成本** — Qwen-VL-Plus ¥0.0015/千tokens，每条短视频约 ¥0.02-0.05。本地部署 Qwen2.5-VL-7B 零成本但需要 8GB+ GPU
- **抖音反爬强度** — 抖音反爬更新频繁，douyin-downloader 可能随时失效。备用方案：手机录屏
- **纯字幕模式降级** — 无视觉模型时信息完整性约 30%
- **版权** — 采集的视频/文章仅供个人学习研究，不重新分发

---

## 快速开始

```
> 收割花叔的所有内容
> 采集抖音 @晓辉博士 的视频并做多模态解析
> 下载这个 YouTube 频道的所有视频然后蒸馏
> harvest @alchaincyf from YouTube and X
```
