"""
测试 API 接口
"""

import requests
import json

BASE_URL = "http://localhost:8080"


def test_health():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    try:
        resp = requests.get(f"{BASE_URL}/api/agent/health")
        print(f"状态码: {resp.status_code}")
        print(f"响应: {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
        return resp.status_code == 200
    except Exception as e:
        print(f"错误: {e}")
        return False


def test_execute():
    """测试执行任务"""
    print("\n=== 测试执行任务 ===")

    payload = {
        "userInput": "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜",
        "sessionId": "test-001"
    }

    print(f"请求: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    try:
        resp = requests.post(
            f"{BASE_URL}/api/agent/execute",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"\n状态码: {resp.status_code}")
        print(f"响应: {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
        return resp.status_code == 200
    except Exception as e:
        print(f"错误: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("  美团 AI Agent API 测试")
    print("=" * 60)

    # 测试健康检查
    health_ok = test_health()

    if health_ok:
        # 测试执行任务
        test_execute()

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
