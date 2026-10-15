from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from bson import ObjectId

from app.schemas.all_schemas import (
    RestaurantResponse,
    MenuItemResponse,
    CreateOrderPayload,
    OrderResponse,
    OrderItemSnapshot,
    RestaurantRegisterPayload,
    RestaurantUpdatePayload,
    MenuItemCreatePayload,
    MenuItemUpdatePayload,
    FoodOrderStatusUpdatePayload
)
from app.database.client import get_database
from app.api.deps import get_current_user, get_optional_current_user
from app.core.rate_limit import check_food_order_rate_limit

router = APIRouter(prefix="/food", tags=["Food Discovery & Ordering"])

# Standard Delivery & Tax pricing policy:
# Fixed flat delivery fee of 3500 paise (Rs. 35)
DELIVERY_FEE_PAISE = 3500
# 5% GST on Restaurant Services
GST_PERCENT = 0.05

VALID_ORDER_STATUSES = ["placed", "confirmed", "preparing", "out_for_delivery", "delivered", "cancelled"]

# 1. Browse Restaurants (Filter by Veg Only, Search, or Service Area)
@router.get("/restaurants", response_model=List[RestaurantResponse])
async def list_restaurants(
    veg_only: bool = Query(False),
    search: Optional[str] = Query(None, max_length=100),
    service_area: Optional[str] = Query(None, max_length=50)
):
    db = get_database()
    if db is None:
        return []

    query: dict = {"is_open": True}
    if veg_only:
        query["is_veg"] = True
    if service_area:
        query["service_area"] = service_area

    if search and search.strip():
        term = search.strip()
        query["$or"] = [
            {"name": {"$regex": term, "$options": "i"}},
            {"cuisine": {"$regex": term, "$options": "i"}}
        ]

    cursor = db.restaurants.find(query)
    restaurants = []
    async for r in cursor:
        restaurants.append(RestaurantResponse(
            id=str(r["_id"]),
            name=r["name"],
            description=r.get("description"),
            service_area=r["service_area"],
            address=r["address"],
            cuisine=r["cuisine"],
            rating=r.get("rating", 4.5),
            time_mins=r.get("time_mins", 25),
            price_for_two_inr=r.get("price_for_two_inr", 400),
            is_veg=r.get("is_veg", False),
            image_url=r.get("image_url"),
            is_open=r.get("is_open", True),
            owner_id=r.get("owner_id")
        ))
    return restaurants

# 2. Get Restaurant Details and Menu
@router.get("/restaurants/{restaurant_id}", response_model=RestaurantResponse)
async def get_restaurant_with_menu(restaurant_id: str):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    restaurant = await db.restaurants.find_one({"_id": restaurant_id})
    if not restaurant:
        try:
            restaurant = await db.restaurants.find_one({"_id": ObjectId(restaurant_id)})
        except Exception:
            pass

    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    # Fetch menu items
    items_cursor = db.menu_items.find({"restaurant_id": restaurant_id})
    menu_list = []
    async for item in items_cursor:
        price_paise = item["price_paise"]
        menu_list.append(MenuItemResponse(
            id=str(item["_id"]),
            restaurant_id=item["restaurant_id"],
            name=item["name"],
            description=item.get("description"),
            price_paise=price_paise,
            price_inr=round(price_paise / 100, 2),
            is_veg=item.get("is_veg", True),
            is_available=item.get("is_available", True),
            category=item.get("category", "Main"),
            image_url=item.get("image_url")
        ))

    return RestaurantResponse(
        id=str(restaurant["_id"]),
        name=restaurant["name"],
        description=restaurant.get("description"),
        service_area=restaurant["service_area"],
        address=restaurant["address"],
        cuisine=restaurant["cuisine"],
        rating=restaurant.get("rating", 4.5),
        time_mins=restaurant.get("time_mins", 25),
        price_for_two_inr=restaurant.get("price_for_two_inr", 400),
        is_veg=restaurant.get("is_veg", False),
        image_url=restaurant.get("image_url"),
        is_open=restaurant.get("is_open", True),
        owner_id=restaurant.get("owner_id"),
        menu=menu_list
    )

# 3. Place Order (Authoritative Server-side Price Validation & Atomic Snapshot)
@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def place_order(
    order_in: CreateOrderPayload,
    current_user: dict = Depends(get_current_user)
):
    check_food_order_rate_limit(current_user["id"])

    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    # Verify restaurant exists & is open
    restaurant = await db.restaurants.find_one({"_id": order_in.restaurant_id})
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if not restaurant.get("is_open", True):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Restaurant is currently closed for orders")

    # Group item quantities from payload
    requested_quantities = {}
    for itm in order_in.items:
        requested_quantities[itm.item_id] = requested_quantities.get(itm.item_id, 0) + itm.quantity

    item_ids = list(requested_quantities.keys())
    db_items_cursor = db.menu_items.find({
        "_id": {"$in": item_ids},
        "restaurant_id": order_in.restaurant_id
    })
    db_items = await db_items_cursor.to_list(length=100)

    if len(db_items) != len(item_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more items do not belong to this restaurant or do not exist"
        )

    # Validate availability & calculate subtotal in paise
    order_item_snapshots: List[OrderItemSnapshot] = []
    subtotal_paise = 0
    total_qty = 0

    for db_item in db_items:
        if not db_item.get("is_available", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item '{db_item['name']}' is currently out of stock and unavailable"
            )

        qty = requested_quantities[str(db_item["_id"])]
        unit_price = db_item["price_paise"]
        item_total = unit_price * qty
        subtotal_paise += item_total
        total_qty += qty

        order_item_snapshots.append(OrderItemSnapshot(
            item_id=str(db_item["_id"]),
            name=db_item["name"],
            unit_price_paise=unit_price,
            quantity=qty,
            total_price_paise=item_total
        ))

    delivery_fee_paise = DELIVERY_FEE_PAISE
    taxes_paise = round(subtotal_paise * GST_PERCENT)
    total_paise = subtotal_paise + delivery_fee_paise + taxes_paise

    now = datetime.now(timezone.utc)
    payment_status = "simulated_paid" if order_in.payment_method.startswith("test_mode") else "pending"

    order_doc = {
        "customer_id": current_user["id"],
        "customer_name": current_user["full_name"],
        "customer_email": current_user["email"],
        "restaurant_id": order_in.restaurant_id,
        "restaurant_name": restaurant["name"],
        "items": [s.model_dump() for s in order_item_snapshots],
        "item_count": total_qty,
        "delivery_address": order_in.delivery_address.strip(),
        "subtotal_paise": subtotal_paise,
        "delivery_fee_paise": delivery_fee_paise,
        "taxes_paise": taxes_paise,
        "total_paise": total_paise,
        "payment_method": order_in.payment_method,
        "payment_status": payment_status,
        "order_status": "placed",
        "created_at": now,
        "updated_at": now
    }

    insert_result = await db.food_orders.insert_one(order_doc)
    order_id = str(insert_result.inserted_id)

    # Trigger notification for customer confirming order placement
    from app.services.notification_service import create_event_notification
    await create_event_notification(
        recipient_user_id=current_user["id"],
        actor_user_id=None,
        category="food",
        event_type="food_order_status",
        title=f"Order Confirmed: {restaurant['name']}",
        desc=f"Your order of {total_qty} items (₹{round(total_paise / 100, 2)}) has been placed successfully.",
        navigation_target=f"food:order:{order_id}",
        metadata={"order_id": order_id, "restaurant_id": order_in.restaurant_id, "order_status": "placed"},
        event_id=f"food_order_placed_{order_id}"
    )

    return OrderResponse(
        id=order_id,
        customer_id=order_doc["customer_id"],
        customer_name=order_doc["customer_name"],
        customer_email=order_doc["customer_email"],
        restaurant_id=order_doc["restaurant_id"],
        restaurant_name=order_doc["restaurant_name"],
        items=order_item_snapshots,
        item_count=order_doc["item_count"],
        delivery_address=order_doc["delivery_address"],
        subtotal_paise=subtotal_paise,
        delivery_fee_paise=delivery_fee_paise,
        taxes_paise=taxes_paise,
        total_paise=total_paise,
        total_inr=round(total_paise / 100, 2),
        payment_method=order_doc["payment_method"],
        payment_status=order_doc["payment_status"],
        order_status=order_doc["order_status"],
        created_at=order_doc["created_at"],
        updated_at=order_doc["updated_at"]
    )

# 4. Get Current User's Orders
@router.get("/orders", response_model=List[OrderResponse])
async def list_customer_orders(
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    cursor = db.food_orders.find({"customer_id": current_user["id"]}).sort("created_at", -1).limit(limit)
    orders = []
    async for doc in cursor:
        items = [OrderItemSnapshot(**it) for it in doc["items"]]
        orders.append(OrderResponse(
            id=str(doc["_id"]),
            customer_id=doc["customer_id"],
            customer_name=doc["customer_name"],
            customer_email=doc["customer_email"],
            restaurant_id=doc["restaurant_id"],
            restaurant_name=doc["restaurant_name"],
            items=items,
            item_count=doc.get("item_count", sum(i.quantity for i in items)),
            delivery_address=doc["delivery_address"],
            subtotal_paise=doc["subtotal_paise"],
            delivery_fee_paise=doc["delivery_fee_paise"],
            taxes_paise=doc["taxes_paise"],
            total_paise=doc["total_paise"],
            total_inr=round(doc["total_paise"] / 100, 2),
            payment_method=doc["payment_method"],
            payment_status=doc["payment_status"],
            order_status=doc["order_status"],
            created_at=doc["created_at"],
            updated_at=doc.get("updated_at", doc["created_at"])
        ))
    return orders

# 5. Get Order Detail (Isolated to Order Owner)
@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order_detail(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        order_obj = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order ID")

    order = await db.food_orders.find_one({"_id": order_obj})
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order["customer_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another customer's order")

    items = [OrderItemSnapshot(**it) for it in order["items"]]
    return OrderResponse(
        id=str(order["_id"]),
        customer_id=order["customer_id"],
        customer_name=order["customer_name"],
        customer_email=order["customer_email"],
        restaurant_id=order["restaurant_id"],
        restaurant_name=order["restaurant_name"],
        items=items,
        item_count=order.get("item_count", sum(i.quantity for i in items)),
        delivery_address=order["delivery_address"],
        subtotal_paise=order["subtotal_paise"],
        delivery_fee_paise=order["delivery_fee_paise"],
        taxes_paise=order["taxes_paise"],
        total_paise=order["total_paise"],
        total_inr=round(order["total_paise"] / 100, 2),
        payment_method=order["payment_method"],
        payment_status=order["payment_status"],
        order_status=order["order_status"],
        created_at=order["created_at"],
        updated_at=order.get("updated_at", order["created_at"])
    )

# 6. Cancel Order (Eligible only when status is 'placed' or 'confirmed')
@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        order_obj = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order ID")

    order = await db.food_orders.find_one({"_id": order_obj})
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order["customer_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot cancel another customer's order")

    if order["order_status"] in ("delivered", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order cannot be cancelled because it is already {order['order_status']}"
        )
    if order["order_status"] in ("preparing", "out_for_delivery"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order is already being prepared or is out for delivery and can no longer be cancelled"
        )

    now = datetime.now(timezone.utc)
    await db.food_orders.update_one(
        {"_id": order_obj},
        {"$set": {"order_status": "cancelled", "updated_at": now}}
    )
    order["order_status"] = "cancelled"
    order["updated_at"] = now

    items = [OrderItemSnapshot(**it) for it in order["items"]]
    return OrderResponse(
        id=str(order["_id"]),
        customer_id=order["customer_id"],
        customer_name=order["customer_name"],
        customer_email=order["customer_email"],
        restaurant_id=order["restaurant_id"],
        restaurant_name=order["restaurant_name"],
        items=items,
        item_count=order.get("item_count", sum(i.quantity for i in items)),
        delivery_address=order["delivery_address"],
        subtotal_paise=order["subtotal_paise"],
        delivery_fee_paise=order["delivery_fee_paise"],
        taxes_paise=order["taxes_paise"],
        total_paise=order["total_paise"],
        total_inr=round(order["total_paise"] / 100, 2),
        payment_method=order["payment_method"],
        payment_status=order["payment_status"],
        order_status="cancelled",
        created_at=order["created_at"],
        updated_at=now
    )


# =======================================================================
# 7. RESTAURANT PARTNER OPERATIONS (Phase 4: Food & Dining Operations)
# =======================================================================

@router.post("/owner/restaurant", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED)
async def register_or_claim_restaurant(
    payload: RestaurantRegisterPayload,
    current_user: dict = Depends(get_current_user)
):
    """Registers a new restaurant under current user's ownership or updates existing profile."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    existing = await db.restaurants.find_one({"owner_id": current_user["id"]})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already owns a registered restaurant."
        )

    now = datetime.now(timezone.utc)
    rest_id = f"rest_{int(now.timestamp())}_{ObjectId()}"
    rest_doc = {
        "_id": rest_id,
        "name": payload.name.strip(),
        "description": payload.description.strip() if payload.description else None,
        "service_area": payload.service_area.strip(),
        "address": payload.address.strip(),
        "cuisine": payload.cuisine.strip(),
        "price_for_two_inr": payload.price_for_two_inr,
        "is_veg": payload.is_veg,
        "image_url": payload.image_url or "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600",
        "rating": 4.8,
        "time_mins": 30,
        "is_open": payload.is_open,
        "owner_id": current_user["id"],
        "created_at": now,
        "updated_at": now
    }

    await db.restaurants.insert_one(rest_doc)

    await db.users.update_one(
        {"_id": ObjectId(current_user["id"])},
        {"$addToSet": {"roles": "restaurant_owner"}}
    )

    return RestaurantResponse(
        id=rest_id,
        name=rest_doc["name"],
        description=rest_doc["description"],
        service_area=rest_doc["service_area"],
        address=rest_doc["address"],
        cuisine=rest_doc["cuisine"],
        rating=rest_doc["rating"],
        time_mins=rest_doc["time_mins"],
        price_for_two_inr=rest_doc["price_for_two_inr"],
        is_veg=rest_doc["is_veg"],
        image_url=rest_doc["image_url"],
        is_open=rest_doc["is_open"],
        owner_id=rest_doc["owner_id"],
        menu=[]
    )


@router.get("/owner/restaurant", response_model=RestaurantResponse)
async def get_owner_restaurant(
    current_user: dict = Depends(get_current_user)
):
    """Fetches the restaurant owned by current authenticated user, including full menu items."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    rest = await db.restaurants.find_one({"owner_id": current_user["id"]})
    if not rest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No restaurant found for current owner")

    rest_id_str = str(rest["_id"])
    items_cursor = db.menu_items.find({"restaurant_id": rest_id_str})
    menu_list = []
    async for item in items_cursor:
        price_paise = item["price_paise"]
        menu_list.append(MenuItemResponse(
            id=str(item["_id"]),
            restaurant_id=item["restaurant_id"],
            name=item["name"],
            description=item.get("description"),
            price_paise=price_paise,
            price_inr=round(price_paise / 100, 2),
            is_veg=item.get("is_veg", True),
            is_available=item.get("is_available", True),
            category=item.get("category", "Main"),
            image_url=item.get("image_url")
        ))

    return RestaurantResponse(
        id=rest_id_str,
        name=rest["name"],
        description=rest.get("description"),
        service_area=rest["service_area"],
        address=rest["address"],
        cuisine=rest["cuisine"],
        rating=rest.get("rating", 4.8),
        time_mins=rest.get("time_mins", 30),
        price_for_two_inr=rest.get("price_for_two_inr", 400),
        is_veg=rest.get("is_veg", False),
        image_url=rest.get("image_url"),
        is_open=rest.get("is_open", True),
        owner_id=rest.get("owner_id"),
        menu=menu_list
    )


@router.patch("/owner/restaurant", response_model=RestaurantResponse)
async def update_owner_restaurant(
    payload: RestaurantUpdatePayload,
    current_user: dict = Depends(get_current_user)
):
    """Updates restaurant profile and opening status with strict ownership enforcement."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    rest = await db.restaurants.find_one({"owner_id": current_user["id"]})
    if not rest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.description is not None:
        updates["description"] = payload.description.strip()
    if payload.service_area is not None:
        updates["service_area"] = payload.service_area.strip()
    if payload.address is not None:
        updates["address"] = payload.address.strip()
    if payload.cuisine is not None:
        updates["cuisine"] = payload.cuisine.strip()
    if payload.price_for_two_inr is not None:
        updates["price_for_two_inr"] = payload.price_for_two_inr
    if payload.is_veg is not None:
        updates["is_veg"] = payload.is_veg
    if payload.image_url is not None:
        updates["image_url"] = payload.image_url
    if payload.is_open is not None:
        updates["is_open"] = payload.is_open

    now = datetime.now(timezone.utc)
    updates["updated_at"] = now

    await db.restaurants.update_one({"_id": rest["_id"]}, {"$set": updates})
    updated_rest = await db.restaurants.find_one({"_id": rest["_id"]})

    rest_id_str = str(updated_rest["_id"])
    items_cursor = db.menu_items.find({"restaurant_id": rest_id_str})
    menu_list = []
    async for item in items_cursor:
        price_paise = item["price_paise"]
        menu_list.append(MenuItemResponse(
            id=str(item["_id"]),
            restaurant_id=item["restaurant_id"],
            name=item["name"],
            description=item.get("description"),
            price_paise=price_paise,
            price_inr=round(price_paise / 100, 2),
            is_veg=item.get("is_veg", True),
            is_available=item.get("is_available", True),
            category=item.get("category", "Main"),
            image_url=item.get("image_url")
        ))

    return RestaurantResponse(
        id=rest_id_str,
        name=updated_rest["name"],
        description=updated_rest.get("description"),
        service_area=updated_rest["service_area"],
        address=updated_rest["address"],
        cuisine=updated_rest["cuisine"],
        rating=updated_rest.get("rating", 4.8),
        time_mins=updated_rest.get("time_mins", 30),
        price_for_two_inr=updated_rest.get("price_for_two_inr", 400),
        is_veg=updated_rest.get("is_veg", False),
        image_url=updated_rest.get("image_url"),
        is_open=updated_rest.get("is_open", True),
        owner_id=updated_rest.get("owner_id"),
        menu=menu_list
    )


@router.post("/owner/menu", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    payload: MenuItemCreatePayload,
    current_user: dict = Depends(get_current_user)
):
    """Adds a new menu item to the owner's restaurant."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    rest = await db.restaurants.find_one({"owner_id": current_user["id"]})
    if not rest:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Must own a restaurant to create menu items")

    rest_id_str = str(rest["_id"])
    now = datetime.now(timezone.utc)
    item_id = f"item_{int(now.timestamp())}_{ObjectId()}"
    item_doc = {
        "_id": item_id,
        "restaurant_id": rest_id_str,
        "name": payload.name.strip(),
        "category": payload.category.strip(),
        "price_paise": payload.price_paise,
        "description": payload.description.strip() if payload.description else None,
        "is_veg": payload.is_veg,
        "is_available": payload.is_available,
        "image_url": payload.image_url or "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=600",
        "created_at": now,
        "updated_at": now
    }

    await db.menu_items.insert_one(item_doc)

    return MenuItemResponse(
        id=item_id,
        restaurant_id=rest_id_str,
        name=item_doc["name"],
        category=item_doc["category"],
        price_paise=item_doc["price_paise"],
        price_inr=round(item_doc["price_paise"] / 100, 2),
        description=item_doc["description"],
        is_veg=item_doc["is_veg"],
        is_available=item_doc["is_available"],
        image_url=item_doc["image_url"]
    )


@router.patch("/owner/menu/{item_id}", response_model=MenuItemResponse)
async def update_menu_item(
    item_id: str,
    payload: MenuItemUpdatePayload,
    current_user: dict = Depends(get_current_user)
):
    """Updates a menu item with strict restaurant ownership verification."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    rest = await db.restaurants.find_one({"owner_id": current_user["id"]})
    if not rest:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    item = await db.menu_items.find_one({"_id": item_id})
    if not item:
        try:
            item = await db.menu_items.find_one({"_id": ObjectId(item_id)})
        except Exception:
            pass

    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")

    if item.get("restaurant_id") != str(rest["_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot edit menu items belonging to another restaurant."
        )

    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.category is not None:
        updates["category"] = payload.category.strip()
    if payload.price_paise is not None:
        updates["price_paise"] = payload.price_paise
    if payload.description is not None:
        updates["description"] = payload.description.strip()
    if payload.is_veg is not None:
        updates["is_veg"] = payload.is_veg
    if payload.is_available is not None:
        updates["is_available"] = payload.is_available
    if payload.image_url is not None:
        updates["image_url"] = payload.image_url

    now = datetime.now(timezone.utc)
    updates["updated_at"] = now

    await db.menu_items.update_one({"_id": item["_id"]}, {"$set": updates})
    updated = await db.menu_items.find_one({"_id": item["_id"]})

    price_paise = updated["price_paise"]
    return MenuItemResponse(
        id=str(updated["_id"]),
        restaurant_id=updated["restaurant_id"],
        name=updated["name"],
        category=updated.get("category", "Main"),
        price_paise=price_paise,
        price_inr=round(price_paise / 100, 2),
        description=updated.get("description"),
        is_veg=updated.get("is_veg", True),
        is_available=updated.get("is_available", True),
        image_url=updated.get("image_url")
    )


@router.delete("/owner/menu/{item_id}")
async def delete_menu_item(
    item_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Deletes or deactivates a menu item belonging to owner's restaurant."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    rest = await db.restaurants.find_one({"owner_id": current_user["id"]})
    if not rest:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    item = await db.menu_items.find_one({"_id": item_id})
    if not item:
        try:
            item = await db.menu_items.find_one({"_id": ObjectId(item_id)})
        except Exception:
            pass

    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")

    if item.get("restaurant_id") != str(rest["_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot delete menu items belonging to another restaurant."
        )

    await db.menu_items.delete_one({"_id": item["_id"]})
    return {"status": "deleted", "item_id": item_id}


@router.get("/owner/orders", response_model=List[OrderResponse])
async def list_restaurant_orders(
    current_user: dict = Depends(get_current_user)
):
    """Lists incoming food orders for the owner's restaurant."""
    db = get_database()
    if db is None:
        return []

    rest = await db.restaurants.find_one({"owner_id": current_user["id"]})
    if not rest:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    rest_id_str = str(rest["_id"])
    cursor = db.food_orders.find({"restaurant_id": rest_id_str}).sort("created_at", -1)
    orders = []
    async for ord_doc in cursor:
        items = [OrderItemSnapshot(**it) for it in ord_doc["items"]]
        orders.append(OrderResponse(
            id=str(ord_doc["_id"]),
            customer_id=ord_doc["customer_id"],
            customer_name=ord_doc["customer_name"],
            customer_email=ord_doc["customer_email"],
            restaurant_id=ord_doc["restaurant_id"],
            restaurant_name=ord_doc["restaurant_name"],
            items=items,
            item_count=ord_doc.get("item_count", sum(i.quantity for i in items)),
            delivery_address=ord_doc["delivery_address"],
            subtotal_paise=ord_doc["subtotal_paise"],
            delivery_fee_paise=ord_doc["delivery_fee_paise"],
            taxes_paise=ord_doc["taxes_paise"],
            total_paise=ord_doc["total_paise"],
            total_inr=round(ord_doc["total_paise"] / 100, 2),
            payment_method=ord_doc["payment_method"],
            payment_status=ord_doc["payment_status"],
            order_status=ord_doc["order_status"],
            created_at=ord_doc["created_at"],
            updated_at=ord_doc.get("updated_at", ord_doc["created_at"])
        ))
    return orders


@router.patch("/owner/orders/{order_id}/status", response_model=OrderResponse)
async def update_restaurant_order_status(
    order_id: str,
    payload: FoodOrderStatusUpdatePayload,
    current_user: dict = Depends(get_current_user)
):
    """Transitions food order status: placed -> confirmed -> preparing -> out_for_delivery -> delivered (or cancelled)."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    rest = await db.restaurants.find_one({"owner_id": current_user["id"]})
    if not rest:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    try:
        order_obj = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order ID")

    order = await db.food_orders.find_one({"_id": order_obj})
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.get("restaurant_id") != str(rest["_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot update orders for another restaurant."
        )

    current_status = order["order_status"]
    new_status = payload.status

    valid_transitions = {
        "placed": ["confirmed", "cancelled"],
        "confirmed": ["preparing", "cancelled"],
        "preparing": ["out_for_delivery"],
        "out_for_delivery": ["delivered"],
        "delivered": [],
        "cancelled": []
    }

    if new_status not in valid_transitions.get(current_status, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid order transition from '{current_status}' to '{new_status}'."
        )

    now = datetime.now(timezone.utc)
    await db.food_orders.update_one(
        {"_id": order_obj},
        {"$set": {"order_status": new_status, "updated_at": now}}
    )
    order["order_status"] = new_status
    order["updated_at"] = now

    # Notification for customer
    from app.services.notification_service import create_event_notification
    await create_event_notification(
        recipient_user_id=order["customer_id"],
        actor_user_id=current_user["id"],
        category="food",
        event_type="food_order_status",
        title=f"Food Order Update: {rest['name']}",
        desc=f"Your order is now {new_status.replace('_', ' ').capitalize()}.",
        navigation_target=f"food:order:{str(order['_id'])}",
        metadata={"order_id": str(order["_id"]), "order_status": new_status},
        event_id=f"food_order_{new_status}_{str(order['_id'])}"
    )

    items = [OrderItemSnapshot(**it) for it in order["items"]]
    return OrderResponse(
        id=str(order["_id"]),
        customer_id=order["customer_id"],
        customer_name=order["customer_name"],
        customer_email=order["customer_email"],
        restaurant_id=order["restaurant_id"],
        restaurant_name=order["restaurant_name"],
        items=items,
        item_count=order.get("item_count", sum(i.quantity for i in items)),
        delivery_address=order["delivery_address"],
        subtotal_paise=order["subtotal_paise"],
        delivery_fee_paise=order["delivery_fee_paise"],
        taxes_paise=order["taxes_paise"],
        total_paise=order["total_paise"],
        total_inr=round(order["total_paise"] / 100, 2),
        payment_method=order["payment_method"],
        payment_status=order["payment_status"],
        order_status=order["order_status"],
        created_at=order["created_at"],
        updated_at=order["updated_at"]
    )

