from fastapi import APIRouter, HTTPException
from api.shared.models import CampaignCreate, CampaignResponse
from api.shared.db import insert_campaign, fetch_campaigns, fetch_campaign_by_id, delete_campaign

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

@router.post("", response_model=CampaignResponse)
async def create_new_campaign(req: CampaignCreate):
    try:
        data = req.model_dump() if hasattr(req, "model_dump") else req.dict()
        campaign = insert_campaign(data)
        return campaign
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(user_id: int):
    try:
        return fetch_campaigns(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: int):
    campaign = fetch_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign

@router.delete("/{campaign_id}")
async def remove_campaign(campaign_id: int):
    deleted = delete_campaign(campaign_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"status": "ok", "deleted": deleted}
