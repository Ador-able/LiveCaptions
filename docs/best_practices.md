# 最佳实践与优化指南 (Optimization Guide)

为了获得最佳的字幕生成和翻译效果，建议对各环节进行如下配置优化。

## 1. 音频前处理 (Audio Pre-processing)

默认使用的 `htdemucs` 模型在速度和效果上取得了平衡，但为了追求极致的人声分离质量（减少背景音对 ASR 的干扰），建议升级模型。

- **推荐模型:** `mdx_extra_q`
  - **优点:** 更高质量的人声分离，尤其是在背景音乐复杂的场景下。
  - **缺点:** 处理速度较慢，显存占用较高。
  - **配置方法:** 修改 `backend/services/audio.py` 中的 `demucs` 命令参数 `-n mdx_extra_q`。

## 2. 语音转写 (ASR - Faster Whisper)

为了最大限度减少幻觉（Hallucinations）并提高准确率，建议调整以下参数：

- **模型选择:** `large-v3` (默认已启用)
- **Beam Size (束搜索):** 建议从默认的 5 增加到 **10**。
  - `beam_size=10`
  - 这会增加解码时间，但能显著提高复杂句子的准确性。
- **VAD 过滤:**
  - 保持 `vad_filter=True`。
  - 建议调整 `min_silence_duration_ms` 为 **1000** (1秒)，避免将短暂的停顿误判为静音，或根据具体音频语速调整。
- **温度 (Temperature):**
  - 建议设置 `temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]`，允许模型在低置信度时自动尝试更高的随机性以寻找更合理的路径。

## 3. 说话人分离 (Diarization)

Pyannote 3.1 是目前的 SOTA 模型。为了提高准确性：

- **指定人数 (Min/Max Speakers):**
  - 如果已知视频中的说话人数量（例如访谈只有2人），**务必**在调用 pipeline 时指定 `min_speakers=2` 和 `max_speakers=2`。这能极大减少错误的说话人聚类。
- **Hugging Face Token:** 确保使用具有访问权限的 Token，且该 Token 已接受 Pyannote 的用户协议。

## 4. LLM 翻译优化 (Prompt Engineering)

为了符合 Netflix 字幕标准，必须在 Prompt 中明确约束 CPL (每行字符数) 和 CPS (每秒字符数)。

### 推荐的三步翻译 Prompt (3-Step Workflow)

#### 第一步：直译 (Literal)
*(保持原代码逻辑，重点在准确性)*

#### 第二步：反思 (Reflection)
*(保持原代码逻辑，重点在一致性)*

#### 第三步：意译与润色 (Polishing - **关键优化**)

```python
step3_prompt = f"""
根据以下信息，重写最终的 {target_lang} 字幕。

严格遵守 Netflix 字幕规范：
1. **长度限制 (CPL):**
   - 英文字幕：每行最多 **42** 个字符。
   - 中文字幕：每行最多 **16** 个汉字。
2. **行数限制:**
   - 必须保持单行或双行，**严禁**出现三行字幕。
3. **语速控制 (CPS):**
   - 译文应简洁，确保观众有足够时间阅读 (中文约 4-6 字/秒)。
4. **格式:**
   - 不要合并原文的独立对话行，保持时间轴对应。
   - 语气自然，符合影视标准。

原文: {source_text}
直译: {literal_trans}
校对意见: {reflection}

只输出最终的翻译结果，不要包含任何解释。
"""
```

## 5. 字幕对齐与分割 (Alignment)

- **Spacy 模型:** 确保使用 `zh_core_web_trf` (Transformer版) 而非 `sm` 版，以获得更精准的中文分词效果（需 GPU 支持）。
- **标点符号:** 在送入 LLM 之前，利用 Spacy 重新修正标点符号，因为 Whisper 生成的标点可能不准确。

## 6. 知识库：Netflix 字幕标准速查

| 指标 | 英文 (English) | 中文 (Chinese) | 说明 |
| :--- | :--- | :--- | :--- |
| **CPL (每行字符)** | Max 42 | Max 16-18 | 超过此长度会导致换行或遮挡画面。 |
| **行数 (Lines)** | Max 2 | Max 2 | 禁止 3 行字幕。 |
| **CPS (字符/秒)** | Max 20 | Max 6-8 | 保证阅读舒适度。 |
| **最短时长** | 0.833s (20帧) | 0.833s | 防止字幕闪烁过快。 |
| **最长时长** | 7.0s | 7.0s | 单条字幕最长显示时间。 |

---

**总结:** 通过升级 Demucs 模型、增加 Whisper Beam Size、指定 Diarization 人数以及在 LLM 提示词中强制 CPL/CPS 约束，可以显著提升字幕生成的专业度和观感。
