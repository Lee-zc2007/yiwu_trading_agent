import argparse
import json

from backend.app.core.database import SessionLocal
from backend.app.models import Transaction
from ml.feature_engineering import extract_order_features
from ml.model_registry import model_registry


def build_training_rows() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with SessionLocal() as db:
        customer_ids = [row[0] for row in db.query(Transaction.customer_id).distinct().all()]
        for customer_id in customer_ids:
            transactions = db.query(Transaction).filter(Transaction.customer_id == customer_id).order_by(Transaction.order_time).all()
            for index, transaction in enumerate(transactions):
                rows.append(extract_order_features(transactions[:index], transaction))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="训练 TradeGuard Isolation Forest")
    parser.add_argument("--contamination", type=float, default=0.08)
    args = parser.parse_args()
    metadata = model_registry.train(build_training_rows(), args.contamination)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
