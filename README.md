# 收割机 · Harvester

> *「字幕只是视频 20% 的信息。我要的是他在说什么的同时做了什么。」*

[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Standard-green)](https://agentskills.io)
[![skills.sh](https://img.shields.io/badge/skills.sh-Compatible-blue)](https://skills.sh)
[![Multi-Runtime](https://img.shields.io/badge/Runtime-Claude%20Code%20·%20Codex%20·%20Hermes-blueviolet)]()

<br>

**输入一个创作者的名字。自动识别他在哪些平台、采集所有内容、用多模态管线解析视频、蒸馏出结构化知识。**

---

## 它和普通下载器的区别

| | yt-dlp / 普通下载器 | 收割机 |
|---|---|---|
| 下载视频 | ✅ | ✅ |
| 提取字幕 | ✅ | ✅ |
| **理解画面内容** | ❌ | ✅ 关键帧 + 视觉模型分析 |
| **时间轴对齐** | ❌ | ✅ 语音+画面精确对齐 |
| **跨平台** | 单平台 | ✅ YouTube/B站/抖音/公众号/X/小红书/知乎 |
| **蒸馏输出** | ❌ | ✅ 全局观点提取 + 方法论总结 |

## 效果对比

**纯字幕模式**（yt-dlp + whisper 字幕）：
```
"今天我们来讲一下 transformer 的注意力机制..."
"attention 的本质是加权求和..."
"代码也很简单，就几行..."
```

**多模态模式**（收割机）：
```
[00:00-00:30] 片头动画 — "Transformer 注意力机制详解"
[00:30-02:15] 老师口述注意力机制的数学定义
  画面：Keynote 幻灯片，公式 QK^T/√d_k 高亮显示
  画面：用动画演示 Q、K、V 三个矩阵的乘法过程
[03:20-05:45] 老师打开 VS Code，逐行讲解 PyTorch 实现
  画面：代码文件 attention.py，老师高亮了 scaled_dot_product_attention 函数
  画面：运行后终端输出 tensor shape，验证维度正确
```

多模态比纯字幕多了：**公式推导的视觉呈现、代码实现的屏幕演示、动画讲解的上下文**。

---

## 安装

```bash
# 1. 安装收割机 skill
npx skills add {owner}/harvester-skill

# 2. 安装依赖工具
pip install yt-dlp openai-whisper scenedetect[opencv] trafilatura

# 3. (可选) 视觉分析 — 任选一个
# Gemini Vision（推荐）
export GEMINI_API_KEY="your-key"
# 或 GPT-4o Vision
export OPENAI_API_KEY="your-key"
# 或本地 Qwen-VL（免费）
pip install transformers qwen-vl-utils
```

## 使用

```
> 收割花叔的所有内容
> 采集抖音 @晓辉博士 的视频并做多模态解析
> harvest @alchaincyf from YouTube and X
> 下载这个 B站 UP 主的所有视频然后蒸馏出一份总结
```

---

## 支持平台

| 平台 | 内容类型 | 依赖工具 |
|------|---------|---------|
| YouTube | 长视频 | yt-dlp |
| B站 | 长视频 | yt-dlp |
| 抖音 | 短视频 | douyin-downloader |
| 公众号 | 长文章 | wechat-article-downloader, trafilatura |
| X/Twitter | 推文 | twikit |
| 小红书 | 图文笔记 | xiaohongshu-crawler |
| 知乎 | 长回答 | trafilatura |
| 通用网页 | 任意 | trafilatura |

---

## 基于 B 站爬虫教程

本 skill 的采集策略来自「7天爬虫从入门到精通」（Yuan老师，44集，18.7小时）：

- Day01-04: HTTP 协议基础 → 构造正确的请求
- Day05: 编码处理 → 中文内容不乱码
- Day06: Cookie/Session → 登录态维持
- Day07-08: 正则 + XPath → 数据提取
- Day09: 代理 IP → 反爬对抗

---

MIT · 2026
