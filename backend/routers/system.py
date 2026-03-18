from fastapi import APIRouter
import torch
from loguru import logger

router = APIRouter()

@router.get("/gpu_status", summary="获取 GPU 状态", description="检查 CUDA 是否可用，并返回显卡详细信息及 PyTorch 版本。")
def get_gpu_status():
    """
    检查显卡资源可用性。
    """
    try:
        is_available = torch.cuda.is_available()
        device_count = torch.cuda.device_count() if is_available else 0
        device_name = torch.cuda.get_device_name(0) if is_available and device_count > 0 else "N/A"
        
        return {
            "available": is_available,
            "device_count": device_count,
            "device_name": device_name,
            "torch_version": torch.__version__
        }
    except Exception as e:
        logger.error(f"Error checking GPU status: {e}")
        return {"error": str(e)}
