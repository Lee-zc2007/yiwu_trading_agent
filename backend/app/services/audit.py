from sqlalchemy.orm import Session

from ..models import AuditLog


def record_audit(
    db: Session,
    merchant_id: int,
    object_type: str,
    object_id: int | str,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
    remark: str = "",
    actor: str = "demo-user",
) -> AuditLog:
    log = AuditLog(
        merchant_id=merchant_id,
        actor=actor,
        object_type=object_type,
        object_id=str(object_id),
        action=action,
        before_data=before or {},
        after_data=after or {},
        remark=remark,
    )
    db.add(log)
    return log
