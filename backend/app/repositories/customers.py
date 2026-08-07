from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import CreditScoreHistory, Customer, Transaction


class CustomerRepository:
    def __init__(self, db: Session, merchant_id: int):
        self.db = db
        self.merchant_id = merchant_id

    def get(self, customer_id: int) -> Customer | None:
        return self.db.query(Customer).filter(Customer.id == customer_id, Customer.merchant_id == self.merchant_id).first()

    def list(self, search: str = "", country: str = "") -> list[Customer]:
        query = self.db.query(Customer).filter(Customer.merchant_id == self.merchant_id)
        if search:
            like = f"%{search}%"
            query = query.filter(or_(Customer.name.ilike(like), Customer.company_name.ilike(like)))
        if country:
            query = query.filter(Customer.country == country)
        return query.order_by(Customer.updated_at.desc()).all()

    def latest_score(self, customer_id: int) -> CreditScoreHistory | None:
        return (
            self.db.query(CreditScoreHistory)
            .filter(CreditScoreHistory.merchant_id == self.merchant_id, CreditScoreHistory.customer_id == customer_id)
            .order_by(CreditScoreHistory.calculated_at.desc(), CreditScoreHistory.id.desc())
            .first()
        )

    def transaction_count(self, customer_id: int) -> int:
        return self.db.query(Transaction).filter(Transaction.merchant_id == self.merchant_id, Transaction.customer_id == customer_id).count()
