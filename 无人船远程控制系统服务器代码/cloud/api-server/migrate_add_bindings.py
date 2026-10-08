"""
数据库迁移脚本: 添加多用户绑定功能
1. 给boats表添加 owner_id, bind_code, bind_enabled 字段
2. 迁移现有数据: user_id -> owner_id, 生成bind_code
3. 为现有船创建 owner 绑定记录
4. 新表会在应用启动时自动创建 (Base.metadata.create_all)

使用方法:
  cd cloud/api-server
  python migrate_add_bindings.py
"""
import sys
import os
import secrets
import string

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base, SessionLocal
from models import Boat, BoatBinding, User
from sqlalchemy import text, inspect


def generate_bind_code(length: int = 6) -> str:
    """生成6位绑定码"""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def column_exists(table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    print("=" * 60)
    print("开始数据库迁移: 添加多用户绑定功能")
    print("=" * 60)

    db = SessionLocal()

    try:
        # 1. 给boats表添加新字段（如果不存在）
        print("\n[1/4] 检查并添加boats表新字段...")

        if not column_exists('boats', 'owner_id'):
            db.execute(text("ALTER TABLE boats ADD COLUMN owner_id INTEGER"))
            print("  - 添加 owner_id 字段")
        else:
            print("  - owner_id 字段已存在")

        if not column_exists('boats', 'bind_code'):
            db.execute(text("ALTER TABLE boats ADD COLUMN bind_code VARCHAR(32)"))
            print("  - 添加 bind_code 字段")
        else:
            print("  - bind_code 字段已存在")

        if not column_exists('boats', 'bind_enabled'):
            db.execute(text("ALTER TABLE boats ADD COLUMN bind_enabled BOOLEAN DEFAULT TRUE"))
            print("  - 添加 bind_enabled 字段")
        else:
            print("  - bind_enabled 字段已存在")

        db.commit()

        # 2. 迁移现有数据: user_id -> owner_id
        print("\n[2/4] 迁移现有船数据...")
        boats = db.query(Boat).all()
        print(f"  - 找到 {len(boats)} 艘船")

        for boat in boats:
            # owner_id = user_id (兼容旧字段)
            if not boat.owner_id and boat.user_id:
                boat.owner_id = boat.user_id
                print(f"  - 船 [{boat.id}] {boat.name}: owner_id = {boat.user_id}")

            # 生成bind_code
            if not boat.bind_code:
                # 确保不重复
                code = generate_bind_code()
                while db.query(Boat).filter(Boat.bind_code == code).first():
                    code = generate_bind_code()
                boat.bind_code = code
                print(f"  - 船 [{boat.id}] {boat.name}: bind_code = {code}")

            # 默认开启绑定
            if boat.bind_enabled is None:
                boat.bind_enabled = True

        db.commit()
        print("  - 船数据迁移完成")

        # 3. 为现有船创建owner绑定记录
        print("\n[3/4] 创建owner绑定记录...")
        for boat in boats:
            existing = db.query(BoatBinding).filter(
                BoatBinding.user_id == boat.owner_id,
                BoatBinding.boat_id == boat.id
            ).first()

            if not existing:
                binding = BoatBinding(
                    user_id=boat.owner_id,
                    boat_id=boat.id,
                    role="owner",
                )
                db.add(binding)
                owner = db.query(User).filter(User.id == boat.owner_id).first()
                print(f"  - 船 [{boat.id}] {boat.name}: 创建owner绑定 -> {owner.username if owner else boat.owner_id}")
            else:
                print(f"  - 船 [{boat.id}] {boat.name}: 绑定记录已存在")

        db.commit()
        print("  - 绑定记录创建完成")

        # 4. 创建新表（通过Base.metadata.create_all）
        print("\n[4/4] 创建新表...")
        Base.metadata.create_all(bind=engine)
        print("  - 新表创建完成 (boat_bindings, boat_bind_requests, boat_control_grants)")

        print("\n" + "=" * 60)
        print("数据库迁移完成!")
        print("=" * 60)

        # 打印迁移结果摘要
        print("\n迁移结果摘要:")
        print(f"  - 船总数: {len(boats)}")
        total_bindings = db.query(BoatBinding).count()
        print(f"  - 绑定记录总数: {total_bindings}")
        for boat in boats:
            owner = db.query(User).filter(User.id == boat.owner_id).first()
            print(f"    * 船 [{boat.id}] {boat.name}: owner={owner.username if owner else '未知'}, bind_code={boat.bind_code}")

    except Exception as e:
        db.rollback()
        print(f"\n迁移失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
