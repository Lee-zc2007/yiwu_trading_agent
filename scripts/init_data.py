import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import Base, SessionLocal, engine  # noqa: E402
from backend.app.data import seed_demo_data  # noqa: E402
from backend.app.models import Customer, Merchant, RiskEvent, Transaction  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化 TradeGuard AI 可复现演示数据")
    parser.add_argument("--reset", action="store_true", help="删除当前数据库中的 TradeGuard 表后重新生成演示数据")
    args = parser.parse_args()
    if args.reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
        print(
            "TradeGuard demo ready: "
            f"merchants={db.query(Merchant).count()}, "
            f"customers={db.query(Customer).count()}, "
            f"transactions={db.query(Transaction).count()}, "
            f"alerts={db.query(RiskEvent).count()}"
        )


if __name__ == "__main__":
    main()
