from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone
from app.schemas.all_schemas import PreferencesModel
from app.api.deps import get_current_user
from app.database.client import get_database

router = APIRouter(prefix="/preferences", tags=["Preferences"])

@router.get("", response_model=PreferencesModel)
async def get_preferences(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return PreferencesModel()

    prefs = await db.user_preferences.find_one({"user_id": current_user["id"]})
    if not prefs:
        return PreferencesModel()

    return PreferencesModel(
        theme=prefs.get("theme", "midnight-glass"),
        appearanceMode=prefs.get("appearanceMode", "system"),
        language=prefs.get("language", "en"),
        accentColor=prefs.get("accentColor", "#8b5cf6"),
        reducedMotion=prefs.get("reducedMotion", False),
        fontSize=prefs.get("fontSize", "normal"),
        compactSidebar=prefs.get("compactSidebar", False),
        currency=prefs.get("currency", "INR"),
        aiMemoryEnabled=prefs.get("aiMemoryEnabled", True),
        pinnedModules=prefs.get("pinnedModules", ["home", "ai-assistant", "search", "chat", "food", "payments"]),
        hiddenModules=prefs.get("hiddenModules", []),
        onboardingCompleted=prefs.get("onboardingCompleted", True)
    )

@router.put("", response_model=PreferencesModel)
async def update_preferences(
    prefs_in: PreferencesModel,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    prefs_dict = prefs_in.model_dump()
    prefs_dict["updated_at"] = datetime.now(timezone.utc)
    prefs_dict["user_id"] = current_user["id"]

    await db.user_preferences.update_one(
        {"user_id": current_user["id"]},
        {"$set": prefs_dict},
        upsert=True
    )

    return prefs_in
