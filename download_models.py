# -*- coding: utf-8 -*-
"""
LiveCaptions 模型下载脚本

下载项目所需的所有 AI 模型到 models/ 目录：
  1. Faster-Whisper large-v2  (语音识别 ASR)
  2. Faster-Whisper large-v3  (语音识别 ASR)
  3. FunASR-Nano  (语音识别 ASR)

使用方法:
  python download_models.py
  python download_models.py --whisper-v2
  python download_models.py --whisper-v3
  python download_models.py --funasr
"""

import os
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
MODELS_DIR = PROJECT_ROOT / "models"

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["MODELSCOPE_SDK_DEBUG"] = "false"


def download_faster_whisper_v2():
    """下载 Faster-Whisper large-v2 模型 (CTranslate2 格式)"""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("❌ 请先安装 huggingface_hub: pip install huggingface_hub")
        sys.exit(1)

    model_id = "Systran/faster-whisper-large-v2"
    local_dir = MODELS_DIR / "faster-whisper" / "large-v2"

    print(f"\n{'='*60}")
    print(f"📥 下载 Faster-Whisper large-v2")
    print(f"   来源: {model_id}")
    print(f"   目标: {local_dir}")
    print(f"{'='*60}")

    if local_dir.exists() and any(local_dir.iterdir()):
        print("✅ 模型目录已存在，跳过下载。如需重新下载请先删除该目录。")
        return

    local_dir.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=model_id,
        local_dir=str(local_dir),
    )
    print("✅ Faster-Whisper large-v2 下载完成！")


def download_faster_whisper_v3():
    """下载 Faster-Whisper large-v3 模型 (CTranslate2 格式)"""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("❌ 请先安装 huggingface_hub: pip install huggingface_hub")
        sys.exit(1)

    model_id = "Systran/faster-whisper-large-v3"
    local_dir = MODELS_DIR / "faster-whisper" / "large-v3"

    print(f"\n{'='*60}")
    print(f"📥 下载 Faster-Whisper large-v3")
    print(f"   来源: {model_id}")
    print(f"   目标: {local_dir}")
    print(f"{'='*60}")

    if local_dir.exists() and any(local_dir.iterdir()):
        print("✅ 模型目录已存在，跳过下载。如需重新下载请先删除该目录。")
        return

    local_dir.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=model_id,
        local_dir=str(local_dir),
    )
    print("✅ Faster-Whisper large-v3 下载完成！")


def download_funasr():
    """下载 FunASR-Nano 模型"""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("❌ 请先安装 huggingface_hub: pip install huggingface_hub")
        sys.exit(1)

    model_id = "FunAudioLLM/Fun-ASR-Nano-2512"
    local_dir = MODELS_DIR / "funasr" / "Fun-ASR-Nano-2512"

    print(f"\n{'='*60}")
    print(f"📥 下载 FunASR-Nano-2512")
    print(f"   来源: {model_id}")
    print(f"   目标: {local_dir}")
    print(f"{'='*60}")

    if local_dir.exists() and any(local_dir.iterdir()):
        print("✅ 模型目录已存在，跳过下载。如需重新下载请先删除该目录。")
        return

    local_dir.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=model_id,
        local_dir=str(local_dir),
    )
    print("✅ FunASR-Nano-2512 下载完成！")


def main():
    parser = argparse.ArgumentParser(description="LiveCaptions 模型下载工具")
    parser.add_argument(
        "--whisper-v2",
        action="store_true",
        help="仅下载 Faster-Whisper v2 模型",
    )
    parser.add_argument(
        "--whisper-v3",
        action="store_true",
        help="仅下载 Faster-Whisper v3 模型",
    )
    parser.add_argument(
        "--funasr",
        action="store_true",
        help="仅下载 FunASR 模型",
    )
    parser.add_argument(
        "--whisper-only",
        action="store_true",
        help="仅下载 Faster-Whisper v2 和 v3 模型",
    )
    args = parser.parse_args()

    print("🚀 LiveCaptions 模型下载工具")
    print(f"   模型目录: {MODELS_DIR}")

    if args.whisper_v2:
        download_faster_whisper_v2()
    elif args.whisper_v3:
        download_faster_whisper_v3()
    elif args.funasr:
        download_funasr()
    elif args.whisper_only:
        download_faster_whisper_v2()
        download_faster_whisper_v3()
    else:
        download_faster_whisper_v2()
        download_faster_whisper_v3()
        download_funasr()

    print(f"\n{'='*60}")
    print("🎉 完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
