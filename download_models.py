# -*- coding: utf-8 -*-
"""
LiveCaptions 模型下载脚本

下载项目所需的所有 AI 模型到 models/ 目录：
  1. Faster-Whisper large-v3  (语音识别 ASR)
  2. Pyannote speaker-diarization-3.1  (说话人分离)
     - pyannote/segmentation-3.0
     - pyannote/wespeaker-voxceleb-resnet34-LM

使用方法:
  python download_models.py

注意:
  - Pyannote 模型是"受限模型"(gated model)，需要先在 HuggingFace 上同意使用条款：
    https://huggingface.co/pyannote/speaker-diarization-3.1
    https://huggingface.co/pyannote/segmentation-3.0
  - 然后设置环境变量 HF_TOKEN 或在 .env 文件中配置你的 HuggingFace Token
"""

import os
import sys
import argparse
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.resolve()
MODELS_DIR = PROJECT_ROOT / "models"


def download_faster_whisper():
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

    if (local_dir / "model.bin").exists():
        print("✅ 模型已存在，跳过下载。如需重新下载请先删除该目录。")
        return

    local_dir.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=model_id,
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
    )
    print("✅ Faster-Whisper large-v3 下载完成！")


def download_pyannote_models(hf_token: str = None):
    """下载 Pyannote 说话人分离相关模型"""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("❌ 请先安装 huggingface_hub: pip install huggingface_hub")
        sys.exit(1)

    # 获取 HuggingFace Token
    if not hf_token:
        hf_token = os.getenv("HF_TOKEN")

    if not hf_token:
        # 尝试从 .env 文件读取
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("HF_TOKEN=") and not line.startswith("#"):
                        hf_token = line.split("=", 1)[1].strip()
                        break

    if not hf_token:
        print("⚠️  未找到 HF_TOKEN。Pyannote 模型为受限模型，需要 HuggingFace Token。")
        print("   请设置环境变量 HF_TOKEN 或在 .env 中配置。")
        print("   跳过 Pyannote 模型下载。")
        return

    hf_home = MODELS_DIR / "huggingface"
    hf_home.mkdir(parents=True, exist_ok=True)

    # 需要下载的 Pyannote 相关模型
    pyannote_models = [
        "pyannote/speaker-diarization-3.1",
        "pyannote/segmentation-3.0",
        "pyannote/wespeaker-voxceleb-resnet34-LM",
    ]

    for model_id in pyannote_models:
        # HuggingFace 缓存结构: models--{org}--{name}
        cache_dir_name = f"models--{model_id.replace('/', '--')}"
        cache_dir = hf_home / cache_dir_name

        print(f"\n{'='*60}")
        print(f"📥 下载 {model_id}")
        print(f"   目标: {cache_dir}")
        print(f"{'='*60}")

        # 检查是否已有 snapshot
        snapshots_dir = cache_dir / "snapshots"
        if snapshots_dir.exists() and any(snapshots_dir.iterdir()):
            print("✅ 模型已存在，跳过下载。如需重新下载请先删除该目录。")
            continue

        try:
            snapshot_download(
                repo_id=model_id,
                cache_dir=str(hf_home),
                token=hf_token,
            )
            print(f"✅ {model_id} 下载完成！")
        except Exception as e:
            print(f"❌ {model_id} 下载失败: {e}")
            print(f"   请确保已在 HuggingFace 上同意该模型的使用条款:")
            print(f"   https://huggingface.co/{model_id}")


def download_torch_checkpoints():
    """
    下载 Pyannote 依赖的 Torch Hub 模型 (speechbrain embeddings)

    这些文件在 Pyannote 首次推理时会自动下载，
    但也可以通过设置 TORCH_HOME 提前缓存。
    """
    print(f"\n{'='*60}")
    print(f"ℹ️  Torch Hub checkpoints (speechbrain 嵌入模型)")
    print(f"   这些文件会在首次运行说话人分离时自动下载。")
    print(f"   如需提前下载，请运行一次说话人分离任务。")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="LiveCaptions 模型下载工具")
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="HuggingFace Token (也可通过 HF_TOKEN 环境变量或 .env 文件设置)",
    )
    parser.add_argument(
        "--whisper-only",
        action="store_true",
        help="仅下载 Faster-Whisper 模型",
    )
    parser.add_argument(
        "--pyannote-only",
        action="store_true",
        help="仅下载 Pyannote 说话人分离模型",
    )
    args = parser.parse_args()

    print("🚀 LiveCaptions 模型下载工具")
    print(f"   模型目录: {MODELS_DIR}")

    if args.whisper_only:
        download_faster_whisper()
    elif args.pyannote_only:
        download_pyannote_models(hf_token=args.token)
    else:
        download_faster_whisper()
        download_pyannote_models(hf_token=args.token)
        download_torch_checkpoints()

    print(f"\n{'='*60}")
    print("🎉 完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
