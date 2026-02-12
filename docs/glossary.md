# 知识库词汇表 (Glossary)

本词汇表解释了字幕制作流程中涉及的关键术语。

## A
- **ASR (Automatic Speech Recognition):** 自动语音识别。本系统使用 `Faster-Whisper` 将语音音频转换为文本。
- **Alignment (对齐):** 将转写的文本与音频的时间轴精确匹配的过程。Whisper 提供字级 (Word-level) 时间戳，用于实现高精度对齐。

## B
- **Beam Search:** 一种搜索算法，用于在生成文本时探索多种可能的路径，选择概率最高的序列。Beam Size 越大，准确率越高，但速度越慢。

## C
- **CPL (Characters Per Line):** 每行字符数。Netflix 标准限制英文约 42 字符，中文约 16-18 字符。
- **CPS (Characters Per Second):** 每秒字符数。衡量字幕阅读速度的指标。过高会导致观众来不及阅读。

## D
- **Demucs:** Meta 开发的音乐源分离模型。本系统中用于提取人声 (Vocals)，去除背景音乐 (BGM) 和噪音。
- **Diarization (说话人分离):** 识别“谁在什么时候说话”的过程。Pyannote 是常用的 Diarization 工具。

## L
- **LLM (Large Language Model):** 大语言模型 (如 GPT-4)。本系统利用 LLM 进行上下文感知的翻译和润色。

## S
- **SRT (SubRip Subtitle):** 最常见的字幕格式，结构简单，包含序号、时间轴和文本。
- **Spacy:** 一个开源的自然语言处理库。本系统用于文本分割 (Segmentation) 和词性标注。

## V
- **VAD (Voice Activity Detection):** 语音活动检测。用于判断一段音频中是否有人说话，过滤静音片段。
- **VTT (WebVTT):** Web Video Text Tracks。HTML5 标准字幕格式，类似于 SRT 但支持更多元数据。

## 为什么需要人声分离？
直接将原视频音频送入 ASR 往往会因为背景音乐、音效的干扰导致识别错误（幻觉）。先使用 Demucs 提取纯净人声，能显著提高 ASR 的准确率。
