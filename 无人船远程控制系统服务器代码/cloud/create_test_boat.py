#!/usr/bin/env python3
"""创建测试船并运行模拟数据生成器"""
import requests
import subprocess
import sys
import time

API_BASE = "http://localhost:8000/api"
TEST_ICCID = "TESTICCID001"
TEST_USER = "testuser"
TEST_PASS = "test123456"


def login():
    """登录获取token"""
    resp = requests.post(f"{API_BASE}/auth/login", json={
        "username": TEST_USER,
        "password": TEST_PASS,
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_boats(token):
    """获取船列表"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{API_BASE}/boats", headers=headers)
    resp.raise_for_status()
    return resp.json()


def create_boat(token):
    """创建测试船"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{API_BASE}/boats", headers=headers, json={
        "name": "模拟测试船",
        "mavlink_sys_id": 1,
        "iccid": TEST_ICCID,
        "description": "模拟数据测试船-用于前端展示",
        "region_id": 1,
    })
    return resp.json()


def main():
    print("=" * 50)
    print("  无人船模拟数据测试")
    print("=" * 50)

    # 1. 登录
    print("\n[1/3] 登录云平台...")
    try:
        token = login()
        print("  登录成功")
    except Exception as e:
        print(f"  登录失败: {e}")
        sys.exit(1)

    # 2. 检查并创建测试船
    print("\n[2/3] 检查测试船...")
    try:
        boats = get_boats(token)
        existing = [b for b in boats if b.get("iccid") == TEST_ICCID]
        if existing:
            boat = existing[0]
            print(f"  测试船已存在: {boat['name']} (id={boat['id']}, boat_key={boat.get('boat_key')})")
        else:
            print("  创建测试船...")
            boat = create_boat(token)
            print(f"  创建成功: {boat['name']} (id={boat['id']}, boat_key={boat.get('boat_key')})")
    except Exception as e:
        print(f"  操作失败: {e}")
        sys.exit(1)

    # 3. 启动模拟数据生成器
    print("\n[3/3] 启动模拟数据生成器...")
    print(f"  ICCID: {TEST_ICCID}")
    print(f"  网关: 127.0.0.1:5760")
    print(f"  初始位置: 22.8037, 113.5333 (广州南沙)")
    print("\n  模拟数据将包括:")
    print("    - 位置 (沿矩形路径移动)")
    print("    - 电池 (电压/电流/剩余电量)")
    print("    - 速度/航向/油门")
    print("    - GPS卫星数/定位质量")
    print("    - 姿态 (横滚/俯仰/偏航)")
    print("    - 饲料余量/4G信号/箱内温度")
    print("\n  按 Ctrl+C 停止")
    print("=" * 50)

    try:
        subprocess.run([
            sys.executable,
            "mock_boat.py",
            "--host", "127.0.0.1",
            "--port", "5760",
            "--iccid", TEST_ICCID,
            "--sys-id", "1",
        ], cwd=r"G:\项目\无人船远程控制系统\cloud")
    except KeyboardInterrupt:
        print("\n\n模拟数据生成器已停止")


if __name__ == "__main__":
    main()
