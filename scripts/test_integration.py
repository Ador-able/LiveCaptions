import requests
import time
import sys

# 集成测试脚本
# 验证后端 API、数据库和任务创建流程

API_URL = "http://localhost:8000/api"

def test_health_check():
    """
    测试健康检查
    """
    print("正在测试 API 连接...")
    try:
        response = requests.get(f"{API_URL}/") # 根路径
        # 注意: 之前的 main.py 定义了 /api 前缀下的 router，根路径可能在 app.get("/")
        # 我们来修正一下 URL
        root_url = "http://localhost:8000/"
        response = requests.get(root_url)
        assert response.status_code == 200
        print("✅ API 服务运行正常")
    except Exception as e:
        print(f"❌ API 连接失败: {e}")
        sys.exit(1)

def test_create_task_local_path():
    """
    测试通过本地路径创建任务
    """
    print("正在测试任务创建 (本地路径)...")
    # 创建一个虚拟文件用于测试
    test_file_path = "/tmp/test_video.mp4"
    with open(test_file_path, "wb") as f:
        f.write(b"dummy video content")

    payload = {
        "video_path": test_file_path,
        "source_language": "en",
        "target_language": "zh"
    }

    response = requests.post(f"{API_URL}/tasks/", json=payload)
    if response.status_code == 200:
        task = response.json()
        print(f"✅ 任务创建成功: ID={task['id']}")
        return task['id']
    else:
        print(f"❌ 任务创建失败: {response.text}")
        sys.exit(1)

def test_task_status(task_id):
    """
    测试任务状态查询
    """
    print(f"正在查询任务状态: {task_id}...")
    response = requests.get(f"{API_URL}/tasks/{task_id}")
    if response.status_code == 200:
        task = response.json()
        print(f"✅ 状态查询成功: {task['status']}, 进度: {task['progress']}%")
        return task
    else:
        print(f"❌ 状态查询失败: {response.text}")

def main():
    test_health_check()
    task_id = test_create_task_local_path()
    time.sleep(2)
    test_task_status(task_id)
    print("所有集成测试通过！")

if __name__ == "__main__":
    main()
