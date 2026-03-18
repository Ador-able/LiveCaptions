import os
import sys
import shutil
import urllib.request
import zipfile
import subprocess
import filecmp
from pathlib import Path


def smart_copytree(src: Path, dst: Path):
    """
    智能复制目录：只复制变更或不存在的文件。
    对比文件大小和修改时间，相同则跳过。
    """
    src = Path(src)
    dst = Path(dst)
    
    dst.mkdir(parents=True, exist_ok=True)
    
    for item in src.iterdir():
        dst_item = dst / item.name
        
        if item.is_dir():
            smart_copytree(item, dst_item)
        else:
            if dst_item.exists():
                # 对比文件：如果大小和修改时间都相同，跳过
                if (item.stat().st_size == dst_item.stat().st_size and 
                    item.stat().st_mtime == dst_item.stat().st_mtime):
                    continue
            shutil.copy2(item, dst_item)

# ---------- 配置 ----------
PROJECT_ROOT = Path(__file__).resolve().parent
BUILD_DIR = PROJECT_ROOT / "build"
PORTABLE_DIR = BUILD_DIR / "LiveCaptions-Portable"

# 使用国内镜像源
PYTHON_URL = "https://npmmirror.com/mirrors/python/3.12.3/python-3.12.3-embed-amd64.zip"
# 改回 GitHub 官方直接下载，避免代理解析不完整问题
REDIS_URL = "https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip"
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
# get-pip 还是使用官方地址，国内访问通常稳定且文件较小
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

def download_file(url, dest):
    """下载文件并显示简单进度。"""
    if dest.exists():
        # 如果是 zip 文件，检查其完整性
        if dest.suffix == ".zip":
            try:
                with zipfile.ZipFile(dest) as z:
                    if z.testzip() is None:
                        print(f"[*] 文件已存在且完整: {dest.name}")
                        return
            except Exception:
                print(f"[!] 发现损坏的 {dest.name}，正在删除并重新下载...")
                dest.unlink()
        else:
            print(f"[*] 文件已存在: {dest.name}")
            return
            
    print(f"[*] 正在下载 {url} ...")
    try:
        urllib.request.urlretrieve(url, dest)
        print(f"[+] 已下载到 {dest}")
    except Exception as e:
        print(f"[!] 下载失败: {e}")
        if dest.exists():
            dest.unlink()  # 删除下载一半的不完整文件
        raise

def extract_zip(zip_path, extract_to):
    """解压 zip 文件。"""
    print(f"[*] 正在解压 {zip_path.name} 到 {extract_to} ...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def setup_python():
    """设置嵌入式 Python 环境并安装依赖。"""
    python_dir = PORTABLE_DIR / "python"
    zip_path = BUILD_DIR / "python-3.12-embed.zip"
    pip_script = BUILD_DIR / "get-pip.py"
    
    # 检查是否需要重新设置 Python 环境
    needs_reinstall = False
    if not (python_dir / "python.exe").exists():
        needs_reinstall = True
    else:
        # 检查是否有损坏的 site-packages
        site_packages = python_dir / "Lib" / "site-packages"
        if site_packages.exists():
            # 检查是否有无效的包（以 ~ 开头的）
            invalid_pkgs = list(site_packages.glob("~*"))
            if invalid_pkgs:
                print(f"[!] 发现损坏的 Python 环境，正在清理...")
                needs_reinstall = True
    
    if needs_reinstall:
        # 清理旧的 Python 目录
        if python_dir.exists():
            shutil.rmtree(python_dir)
        python_dir.mkdir(parents=True, exist_ok=True)
        
        download_file(PYTHON_URL, zip_path)
        extract_zip(zip_path, python_dir)

        # 通过取消 python312._pth 中的 #import site 注释来启用 site-packages
        pth_file = python_dir / "python312._pth"
        if pth_file.exists():
            lines = pth_file.read_text(encoding="utf-8").splitlines()
            new_lines = []
            for line in lines:
                if line.strip() == "#import site":
                    new_lines.append("import site")
                else:
                    new_lines.append(line)
            pth_file.write_text("\n".join(new_lines), encoding="utf-8")
            print("[+] 已在 python312._pth 中启用 site-packages")

    download_file(GET_PIP_URL, pip_script)

    python_exe = python_dir / "python.exe"
    
    # 检查 pip 是否已经安装
    pip_installed = False
    try:
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            pip_installed = True
            print(f"[*] pip 已安装: {result.stdout.strip()}")
    except Exception:
        pass
    
    # 安装或重新安装 pip
    if not pip_installed:
        print("[*] 正在安装 pip...")
        subprocess.run([str(python_exe), str(pip_script), "--force-reinstall"], check=True)

    # 使用嵌入式 Python 的 pip 安装项目依赖
    print("[*] 正在安装项目依赖...")
    req_file = PROJECT_ROOT / "backend" / "requirements.txt"
    
    # 设置 PyPI 国内镜像源以加速下载，并增加超时时间
    pip_cmd = [str(python_exe), "-m", "pip", "install", 
               "-i", "https://mirrors.aliyun.com/pypi/simple/", 
               "--trusted-host", "mirrors.aliyun.com",
               "--timeout", "120",
               "--retries", "3"]
    
    print("[*] 正在升级 pip...")
    subprocess.run(pip_cmd + ["--upgrade", "pip"], check=True)
    
    # 安装 setuptools 和 wheel，这是构建许多 Python 包所必需的
    print("[*] 正在安装构建基础工具 (setuptools, wheel)...")
    subprocess.run(pip_cmd + ["setuptools", "wheel"], check=True)
    
    # 安装项目依赖
    print("[*] 正在安装项目依赖 (这可能需要较长时间)...")
    install_reqs_cmd = pip_cmd + [
        "--find-links", "https://mirrors.aliyun.com/pytorch-wheels/cu128",
        "-r", str(req_file)
    ]
    try:
        subprocess.run(install_reqs_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] 依赖安装失败，尝试备用方案...")
        # 尝试不使用 find-links
        install_reqs_cmd_fallback = pip_cmd + ["-r", str(req_file)]
        subprocess.run(install_reqs_cmd_fallback, check=True)
    print("[+] Python 环境设置完成。")

def setup_redis():
    """下载并设置 Redis。"""
    redis_dir = PORTABLE_DIR / "redis"
    redis_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = BUILD_DIR / "redis.zip"
    download_file(REDIS_URL, zip_path)
    
    if not (redis_dir / "redis-server.exe").exists():
        extract_dir = BUILD_DIR / "redis_extracted"
        extract_zip(zip_path, extract_dir)
        
        # 拷贝必要的 Redis 文件
        for file_name in ["redis-server.exe", "redis-cli.exe", "redis.windows.conf"]:
            files = list(extract_dir.glob(f"**/{file_name}"))
            if files:
                shutil.copy2(files[0], redis_dir / file_name)
        print("[+] Redis 设置完成。")

def setup_ffmpeg():
    """下载并设置 FFmpeg。"""
    ffmpeg_dir = PORTABLE_DIR / "ffmpeg"
    ffmpeg_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin_dir = ffmpeg_dir / "bin"
    ffmpeg_bin_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = BUILD_DIR / "ffmpeg.zip"
    download_file(FFMPEG_URL, zip_path)
    
    if not (ffmpeg_bin_dir / "ffmpeg.exe").exists():
        extract_dir = BUILD_DIR / "ffmpeg_extracted"
        extract_zip(zip_path, extract_dir)
        
        # 寻找 bin 目录并拷贝文件
        for file_name in ["ffmpeg.exe", "ffprobe.exe"]:
            files = list(extract_dir.glob(f"**/bin/{file_name}"))
            if files:
                shutil.copy2(files[0], ffmpeg_bin_dir / file_name)
        print("[+] FFmpeg 设置完成。")

def build_frontend():
    """使用 npm 构建前端。"""
    frontend_dir = PROJECT_ROOT / "frontend"
    print("[*] 正在构建前端。这需要您的机器已安装 Node.js...")
    subprocess.run(["npm", "install", "--legacy-peer-deps", "--registry=https://registry.npmmirror.com"], cwd=str(frontend_dir), check=True, shell=True)
    subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), check=True, shell=True)
    print("[+] 前端构建完成。")

def copy_project_files():
    """将后端、前端、模型等内容拷贝到绿色版目录。"""
    print("[*] 正在拷贝项目文件...")
    
    # 1. 后端
    backend_src = PROJECT_ROOT / "backend"
    backend_dst = PORTABLE_DIR / "backend"
    if backend_dst.exists():
        shutil.rmtree(backend_dst)
    shutil.copytree(backend_src, backend_dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    
    # 2. 前端 Dist
    frontend_dist_src = PROJECT_ROOT / "frontend" / "dist"
    frontend_dist_dst = PORTABLE_DIR / "frontend" / "dist"
    if frontend_dist_dst.exists():
        shutil.rmtree(frontend_dist_dst)
    if frontend_dist_src.exists():
        shutil.copytree(frontend_dist_src, frontend_dist_dst)
    
    # 3. 模型
    models_src = PROJECT_ROOT / "models"
    models_dst = PORTABLE_DIR / "models"
    if not models_dst.exists():
        models_dst.mkdir(parents=True)
    
    if models_src.exists():
        print("[*] 正在拷贝模型文件，这可能需要较长时间...")
        smart_copytree(models_src, models_dst)
    else:
        print("[!] 警告: 未找到 'models' 目录。")
        
    # 4. 数据目录初始化
    data_dst = PORTABLE_DIR / "data"
    data_dst.mkdir(exist_ok=True)
    (data_dst / "uploads").mkdir(exist_ok=True)
    (data_dst / "results").mkdir(exist_ok=True)
    
    # 5. 环境变量文件
    env_src = PROJECT_ROOT / ".env"
    env_dst = PORTABLE_DIR / ".env"
    if env_src.exists():
        env_content = env_src.read_text(encoding="utf-8")
        
        # 强制覆盖为便携版相对路径的配置
        overrides = {
            "DATABASE_URL": "sqlite:///./data/tasks.db",
            "REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/0",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
            "CELERY_TIMEZONE": "Asia/Shanghai",
            "HF_HOME": "./models/huggingface",
            "HF_HUB_OFFLINE": "1",
            "TORCH_HOME": "./models/torch",
            "WHISPER_MODEL_V2_PATH": "./models/faster-whisper/large-v2",
            "WHISPER_MODEL_V3_PATH": "./models/faster-whisper/large-v3",
            "DEMUCS_MODEL": "htdemucs_ft",
            "DEMUCS_DEVICE": "cuda",
            "DEMUCS_SEGMENT": "7",
            "UPLOAD_DIR": "./data/uploads",
            "RESULT_DIR": "./data/results",
            "HOST": "0.0.0.0",
            "PORT": "8000"
        }
        
        new_lines = []
        seen_keys = set()
        for line in env_content.splitlines():
            line_stripped = line.strip()
            # 找到 key=value 形式，且未被注释的
            if line_stripped and not line_stripped.startswith("#") and "=" in line_stripped:
                key = line_stripped.split("=", 1)[0].strip()
                if key in overrides:
                    new_lines.append(f"{key}={overrides[key]}")
                    seen_keys.add(key)
                    continue
            new_lines.append(line)
            
        # 把原始文件里缺少，但是 overrides 必需的配置加在末尾
        for k, v in overrides.items():
            if k not in seen_keys:
                new_lines.append(f"{k}={v}")
                
        env_dst.write_text("\n".join(new_lines), encoding="utf-8")
    else:
        default_env = """
DATABASE_URL=sqlite:///./data/tasks.db
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TIMEZONE=Asia/Shanghai

HF_HOME=./models/huggingface
HF_HUB_OFFLINE=1
TORCH_HOME=./models/torch
WHISPER_MODEL_V2_PATH=./models/faster-whisper/large-v2
WHISPER_MODEL_V3_PATH=./models/faster-whisper/large-v3
FUNASR_MODEL_PATH=./models/funasr/Fun-ASR-Nano-2512

DEMUCS_MODEL=htdemucs_ft
DEMUCS_DEVICE=cuda
DEMUCS_SEGMENT=7

UPLOAD_DIR=./data/uploads
RESULT_DIR=./data/results

HOST=0.0.0.0
PORT=8000
"""
        env_dst.write_text(default_env.strip(), encoding="utf-8")
        
    print("[+] 项目文件拷贝完成。")

def create_scripts():
    """创建启动和停止脚本。"""
    print("[*] 正在创建控制脚本...")
    
    start_bat = PORTABLE_DIR / "start.bat"
    # 使用 raw string 避免转义问题
    start_bat_content = r"""@echo off
chcp 65001 >nul
setlocal

title LiveCaptions 绿色版服务器

cd /d "%~dp0"

:: 将便携式 Python 和 FFmpeg 加入路径
set PATH=%~dp0python;%~dp0python\Scripts;%~dp0ffmpeg\bin;%PATH%

:: 环境变量隔离 (防止与机器上的全局 Python 安装冲突)
set PYTHONNOUSERSITE=1
set PYTHONPATH=%~dp0

:: 设置运行模型路径与国内镜像源
set HF_HOME=%~dp0models\huggingface
set TORCH_HOME=%~dp0models\torch
set HF_ENDPOINT=https://hf-mirror.com

echo ===================================================
echo   正在启动 LiveCaptions 绿色版环境
echo ===================================================

echo [1/3] 正在启动 Redis 数据库服务...
start "Redis Server" /B "%~dp0redis\redis-server.exe" "%~dp0redis\redis.windows.conf" >nul 2>&1

:: 等待 Redis 初始化结束
timeout /t 2 /nobreak >nul

echo [2/3] 正在启动 Celery Worker 后台处理任务...
start "Celery Worker" /B "%~dp0python\python.exe" -m celery -A backend.worker.celery_app worker --loglevel=info --concurrency=1 --pool=solo

echo [3/3] 正在启动 FastAPI 后端服务 (包含前端面板)...
"%~dp0python\python.exe" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

endlocal
"""
    # 强制以 UTF-8 写入并通过 chcp 65001 保障中文正常显示
    start_bat.write_text(start_bat_content, encoding="utf-8")

    stop_bat = PORTABLE_DIR / "stop.bat"
    stop_bat_content = r"""@echo off
chcp 65001 >nul
setlocal

echo 正在停止 LiveCaptions 相关进程...

taskkill /F /IM uvicorn.exe /T 2>nul
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM redis-server.exe /T 2>nul

echo 所有服务已停止。
pause
"""
    stop_bat.write_text(stop_bat_content, encoding="utf-8")
    print("[+] 控制脚本创建完成。")

def main():
    print("=" * 60)
    print("      正在构建 LiveCaptions 绿色版集成包      ")
    print("=" * 60)
    
    # 检查是否需要清理
    clean_build = False
    if len(sys.argv) > 1 and sys.argv[1] in ["--clean", "-c"]:
        clean_build = True
        print("[*] 使用 --clean 模式，将删除现有 build 目录并重新开始")
    
    if clean_build and BUILD_DIR.exists():
        print(f"[*] 正在删除旧的 build 目录...")
        shutil.rmtree(BUILD_DIR)
    
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    PORTABLE_DIR.mkdir(parents=True, exist_ok=True)

    # 设置当前进程的 HuggingFace 镜像
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    # 隔离全局包，防止 pip 忽略在全局中已经存在的包
    os.environ["PYTHONNOUSERSITE"] = "1"

    try:
        setup_python()
        setup_redis()
        setup_ffmpeg()
        build_frontend()
        copy_project_files()
        create_scripts()

        print("=" * 60)
        print(f" 构建圆满完成! 绿色版目录位于:\n {PORTABLE_DIR.resolve()}")
        print("=" * 60)
    except Exception as e:
        print(f"\n[!] 构建过程中出现错误: {e}")
        print(f"\n提示: 可以尝试使用 'python build_portable.py --clean' 来完全重新构建")
        sys.exit(1)

if __name__ == "__main__":
    main()
