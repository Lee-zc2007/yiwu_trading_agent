"""社会实践三分钟路演 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.common import ApiResponse
from ...schemas.demo import RoadshowAgentResponse, RoadshowAnalyzeResponse, RoadshowScenarioResponse
from ...services.roadshow_demo import RoadshowDemoService
from ..dependencies import get_merchant_id


router = APIRouter(prefix="/api/demo", tags=["三分钟路演"])


def _service(db: Session, merchant_id: int) -> RoadshowDemoService:
    return RoadshowDemoService(db, merchant_id)


@router.get("/scenario", response_model=ApiResponse[RoadshowScenarioResponse])
def get_scenario(merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    try:
        return {"data": _service(db, merchant_id).scenario()}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/analyze", response_model=ApiResponse[RoadshowAnalyzeResponse])
def analyze_scenario(merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    try:
        return {"data": _service(db, merchant_id).analyze(), "message": "演示风险分析完成；未写入业务数据"}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/agent", response_model=ApiResponse[RoadshowAgentResponse])
def run_demo_agent(merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    try:
        return {"data": _service(db, merchant_id).run_agent(), "message": "演示 Agent 调用完成；未保存会话"}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
