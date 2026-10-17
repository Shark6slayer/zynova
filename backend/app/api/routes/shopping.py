from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from bson import ObjectId

from app.schemas.all_schemas import (
    ProductResponse,
    CreateShoppingOrderPayload,
    ShoppingOrderResponse,
    ShoppingOrderItemSnapshot,
    SellerRegisterPayload,
    SellerResponse,
    SellerDashboardResponse,
    ProductCreatePayload,
    ProductUpdatePayload,
    SellerOrderStatusUpdatePayload
)
from app.database.client import get_database
from app.api.deps import get_current_user
from app.core.rate_limit import check_shopping_order_rate_limit
from app.core.audit_ledger import record_audit_event

router = APIRouter(prefix="/shopping", tags=["Shopping & E-Commerce"])

# Shipping & Tax Policy for Products:
# Standard Flat Shipping of 4900 paise (₹49)
# Free shipping above ₹999 (99900 paise)
FREE_SHIPPING_THRESHOLD_PAISE = 99900
STANDARD_SHIPPING_PAISE = 4900
# 18% GST for Consumer Electronics & Retail Goods
GST_PERCENT = 0.18

VALID_ORDER_STATUSES = ["placed", "confirmed", "processing", "shipped", "delivered", "cancelled"]

# 1. List Products with Search, Category Filter, Price Range Filter, Sorting & Pagination
@router.get("/products", response_model=List[ProductResponse])
async def list_products(
    category: Optional[str] = Query(None, max_length=50),
    search: Optional[str] = Query(None, max_length=100),
    min_price: Optional[int] = Query(None, ge=0),
    max_price: Optional[int] = Query(None, ge=0),
    sort: Optional[str] = Query("featured", pattern="^(featured|price_asc|price_desc|rating|newest)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50)
):
    db = get_database()
    if db is None:
        return []

    query: dict = {"is_published": True}

    if category and category.strip() and category.lower() != "all":
        query["category"] = {"$regex": f"^{category.strip()}$", "$options": "i"}

    if min_price is not None or max_price is not None:
        price_query = {}
        if min_price is not None:
            price_query["$gte"] = min_price
        if max_price is not None:
            price_query["$lte"] = max_price
        query["price_paise"] = price_query

    if search and search.strip():
        term = search.strip()
        query["$or"] = [
            {"name": {"$regex": term, "$options": "i"}},
            {"brand": {"$regex": term, "$options": "i"}},
            {"description": {"$regex": term, "$options": "i"}},
            {"sku": {"$regex": term, "$options": "i"}}
        ]

    # Sorting
    sort_fields = [("created_at", -1)]
    if sort == "price_asc":
        sort_fields = [("price_paise", 1)]
    elif sort == "price_desc":
        sort_fields = [("price_paise", -1)]
    elif sort == "rating":
        sort_fields = [("rating", -1)]
    elif sort == "newest":
        sort_fields = [("created_at", -1)]

    skip = (page - 1) * limit
    cursor = db.products.find(query).sort(sort_fields).skip(skip).limit(limit)

    products = []
    async for p in cursor:
        price_p = p["price_paise"]
        mrp_p = p.get("mrp_paise")
        products.append(ProductResponse(
            id=str(p["_id"]),
            name=p["name"],
            brand=p.get("brand", "Generic"),
            sku=p.get("sku", ""),
            category=p.get("category", "General"),
            description=p.get("description", ""),
            price_paise=price_p,
            price_inr=round(price_p / 100, 2),
            mrp_paise=mrp_p,
            mrp_inr=round(mrp_p / 100, 2) if mrp_p else None,
            rating=p.get("rating", 4.5),
            reviews_count=p.get("reviews_count", 0),
            stock=p.get("stock", 0),
            is_available=p.get("is_available", True) and p.get("stock", 0) > 0,
            is_published=p.get("is_published", True),
            is_seed_data=p.get("is_seed_data", True),
            seller_id=p.get("seller_id"),
            seller_name=p.get("seller_name"),
            images=p.get("images", []),
            features=p.get("features", []),
            created_at=p.get("created_at", datetime.now(timezone.utc)),
            updated_at=p.get("updated_at", datetime.now(timezone.utc))
        ))
    return products

# 2. Get Product Detail
@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product_detail(product_id: str):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    p = await db.products.find_one({"_id": product_id, "is_published": True})
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or not published"
        )

    price_p = p["price_paise"]
    mrp_p = p.get("mrp_paise")
    return ProductResponse(
        id=str(p["_id"]),
        name=p["name"],
        brand=p.get("brand", "Generic"),
        sku=p.get("sku", ""),
        category=p.get("category", "General"),
        description=p.get("description", ""),
        price_paise=price_p,
        price_inr=round(price_p / 100, 2),
        mrp_paise=mrp_p,
        mrp_inr=round(mrp_p / 100, 2) if mrp_p else None,
        rating=p.get("rating", 4.5),
        reviews_count=p.get("reviews_count", 0),
        stock=p.get("stock", 0),
        is_available=p.get("is_available", True) and p.get("stock", 0) > 0,
        is_published=p.get("is_published", True),
        is_seed_data=p.get("is_seed_data", True),
        seller_id=p.get("seller_id"),
        seller_name=p.get("seller_name"),
        images=p.get("images", []),
        features=p.get("features", []),
        created_at=p.get("created_at", datetime.now(timezone.utc)),
        updated_at=p.get("updated_at", datetime.now(timezone.utc))
    )

# 3. Create / Place Shopping Order (Atomic Inventory Decrement, Idempotency, Strict Server Calculations)
@router.post("/orders", response_model=ShoppingOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_shopping_order(
    payload: CreateShoppingOrderPayload,
    current_user: dict = Depends(get_current_user)
):
    check_shopping_order_rate_limit(current_user["id"])

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    # Idempotency check: if client provided an idempotency key and order exists, return existing order
    if payload.idempotency_key:
        existing_order = await db.shopping_orders.find_one({
            "idempotency_key": payload.idempotency_key,
            "customer_id": current_user["id"]
        })
        if existing_order:
            items = [ShoppingOrderItemSnapshot(**it) for it in existing_order["items"]]
            return ShoppingOrderResponse(
                id=str(existing_order["_id"]),
                customer_id=existing_order["customer_id"],
                customer_name=existing_order["customer_name"],
                customer_email=existing_order["customer_email"],
                shipping_full_name=existing_order["shipping_full_name"],
                shipping_phone=existing_order["shipping_phone"],
                shipping_address=existing_order["shipping_address"],
                shipping_city=existing_order["shipping_city"],
                shipping_postal_code=existing_order["shipping_postal_code"],
                items=items,
                total_items_count=existing_order["total_items_count"],
                subtotal_paise=existing_order["subtotal_paise"],
                shipping_paise=existing_order["shipping_paise"],
                taxes_paise=existing_order["taxes_paise"],
                discount_paise=existing_order.get("discount_paise", 0),
                total_paise=existing_order["total_paise"],
                total_inr=round(existing_order["total_paise"] / 100, 2),
                payment_method=existing_order["payment_method"],
                payment_status=existing_order["payment_status"],
                order_status=existing_order["order_status"],
                idempotency_key=existing_order.get("idempotency_key"),
                created_at=existing_order["created_at"],
                updated_at=existing_order["updated_at"]
            )

    # Consolidate items by product_id
    requested_quantities = {}
    for item in payload.items:
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
        requested_quantities[item.product_id] = requested_quantities.get(item.product_id, 0) + item.quantity

    product_ids = list(requested_quantities.keys())
    db_products = await db.products.find({"_id": {"$in": product_ids}, "is_published": True}).to_list(length=100)

    if len(db_products) != len(product_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more products in your cart do not exist or are unpublished."
        )

    product_dict = {str(p["_id"]): p for p in db_products}

    # Pre-check initial stock & availability
    for pid, qty in requested_quantities.items():
        prod = product_dict[pid]
        if not prod.get("is_available", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{prod['name']}' is currently not available for purchase."
            )
        if prod.get("stock", 0) < qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for '{prod['name']}'. Requested: {qty}, Available: {prod.get('stock', 0)}."
            )

    # Perform atomic stock reservation for all items
    reserved_items = []
    for pid, qty in requested_quantities.items():
        res = await db.products.update_one(
            {"_id": pid, "stock": {"$gte": qty}},
            {"$inc": {"stock": -qty}}
        )
        if res.modified_count == 0:
            # Atomic decrement failed! Compensate and restore previous reservations
            for r_pid, r_qty in reserved_items:
                await db.products.update_one({"_id": r_pid}, {"$inc": {"stock": r_qty}})
            prod = product_dict[pid]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock just ran out for '{prod['name']}' due to concurrent demand. Please adjust quantity."
            )
        reserved_items.append((pid, qty))

    # Calculate authoritative financial snapshot in integer paise
    subtotal_paise = 0
    total_items_count = 0
    item_snapshots: List[ShoppingOrderItemSnapshot] = []

    for pid, qty in requested_quantities.items():
        prod = product_dict[pid]
        unit_price = prod["price_paise"]
        item_total = unit_price * qty
        subtotal_paise += item_total
        total_items_count += qty

        item_snapshots.append(ShoppingOrderItemSnapshot(
            product_id=pid,
            name=prod["name"],
            sku=prod.get("sku", ""),
            brand=prod.get("brand", "Generic"),
            unit_price_paise=unit_price,
            quantity=qty,
            total_price_paise=item_total,
            image_url=prod["images"][0] if prod.get("images") else None,
            seller_id=prod.get("seller_id")
        ))

    shipping_paise = 0 if subtotal_paise >= FREE_SHIPPING_THRESHOLD_PAISE else STANDARD_SHIPPING_PAISE
    taxes_paise = round(subtotal_paise * GST_PERCENT)
    total_paise = subtotal_paise + shipping_paise + taxes_paise

    now = datetime.now(timezone.utc)
    payment_status = "simulated_paid" if payload.payment_method.startswith("test_mode") else "pending"

    order_doc = {
        "customer_id": current_user["id"],
        "customer_name": current_user["full_name"],
        "customer_email": current_user["email"],
        "shipping_full_name": payload.shipping_full_name.strip(),
        "shipping_phone": payload.shipping_phone.strip(),
        "shipping_address": payload.shipping_address.strip(),
        "shipping_city": payload.shipping_city.strip(),
        "shipping_postal_code": payload.shipping_postal_code.strip(),
        "items": [s.model_dump() for s in item_snapshots],
        "total_items_count": total_items_count,
        "subtotal_paise": subtotal_paise,
        "shipping_paise": shipping_paise,
        "taxes_paise": taxes_paise,
        "discount_paise": 0,
        "total_paise": total_paise,
        "payment_method": payload.payment_method,
        "payment_status": payment_status,
        "order_status": "placed",
        "idempotency_key": payload.idempotency_key,
        "created_at": now,
        "updated_at": now
    }

    insert_result = await db.shopping_orders.insert_one(order_doc)
    order_id = str(insert_result.inserted_id)

    # Trigger notification for customer confirming shopping order placement
    from app.services.notification_service import create_event_notification
    await create_event_notification(
        recipient_user_id=current_user["id"],
        actor_user_id=None,
        category="shopping",
        event_type="shopping_order_status",
        title=f"Order Placed: #{order_id[-8:]}",
        desc=f"Your order of {total_items_count} item(s) (₹{round(total_paise / 100, 2)}) has been confirmed and reserved.",
        navigation_target=f"shopping:order:{order_id}",
        metadata={"order_id": order_id, "total_items_count": total_items_count, "order_status": "placed"},
        event_id=f"shopping_order_placed_{order_id}"
    )

    return ShoppingOrderResponse(
        id=order_id,
        customer_id=order_doc["customer_id"],
        customer_name=order_doc["customer_name"],
        customer_email=order_doc["customer_email"],
        shipping_full_name=order_doc["shipping_full_name"],
        shipping_phone=order_doc["shipping_phone"],
        shipping_address=order_doc["shipping_address"],
        shipping_city=order_doc["shipping_city"],
        shipping_postal_code=order_doc["shipping_postal_code"],
        items=item_snapshots,
        total_items_count=total_items_count,
        subtotal_paise=subtotal_paise,
        shipping_paise=shipping_paise,
        taxes_paise=taxes_paise,
        discount_paise=0,
        total_paise=total_paise,
        total_inr=round(total_paise / 100, 2),
        payment_method=order_doc["payment_method"],
        payment_status=order_doc["payment_status"],
        order_status=order_doc["order_status"],
        idempotency_key=order_doc.get("idempotency_key"),
        created_at=order_doc["created_at"],
        updated_at=order_doc["updated_at"]
    )

# 4. Get Authenticated Customer's Order History
@router.get("/orders", response_model=List[ShoppingOrderResponse])
async def list_customer_orders(
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    cursor = db.shopping_orders.find({"customer_id": current_user["id"]}).sort("created_at", -1).limit(limit)
    orders = []
    async for doc in cursor:
        items = [ShoppingOrderItemSnapshot(**it) for it in doc["items"]]
        orders.append(ShoppingOrderResponse(
            id=str(doc["_id"]),
            customer_id=doc["customer_id"],
            customer_name=doc["customer_name"],
            customer_email=doc["customer_email"],
            shipping_full_name=doc["shipping_full_name"],
            shipping_phone=doc["shipping_phone"],
            shipping_address=doc["shipping_address"],
            shipping_city=doc["shipping_city"],
            shipping_postal_code=doc["shipping_postal_code"],
            items=items,
            total_items_count=doc["total_items_count"],
            subtotal_paise=doc["subtotal_paise"],
            shipping_paise=doc["shipping_paise"],
            taxes_paise=doc["taxes_paise"],
            discount_paise=doc.get("discount_paise", 0),
            total_paise=doc["total_paise"],
            total_inr=round(doc["total_paise"] / 100, 2),
            payment_method=doc["payment_method"],
            payment_status=doc["payment_status"],
            order_status=doc["order_status"],
            idempotency_key=doc.get("idempotency_key"),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"]
        ))
    return orders

# 5. Get Order Details (Strict Ownership Check)
@router.get("/orders/{order_id}", response_model=ShoppingOrderResponse)
async def get_order_detail(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        obj_id = ObjectId(order_id)
        query = {"_id": obj_id}
    except Exception:
        query = {"_id": order_id}

    order = await db.shopping_orders.find_one(query)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order["customer_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this order")

    items = [ShoppingOrderItemSnapshot(**it) for it in order["items"]]
    return ShoppingOrderResponse(
        id=str(order["_id"]),
        customer_id=order["customer_id"],
        customer_name=order["customer_name"],
        customer_email=order["customer_email"],
        shipping_full_name=order["shipping_full_name"],
        shipping_phone=order["shipping_phone"],
        shipping_address=order["shipping_address"],
        shipping_city=order["shipping_city"],
        shipping_postal_code=order["shipping_postal_code"],
        items=items,
        total_items_count=order["total_items_count"],
        subtotal_paise=order["subtotal_paise"],
        shipping_paise=order["shipping_paise"],
        taxes_paise=order["taxes_paise"],
        discount_paise=order.get("discount_paise", 0),
        total_paise=order["total_paise"],
        total_inr=round(order["total_paise"] / 100, 2),
        payment_method=order["payment_method"],
        payment_status=order["payment_status"],
        order_status=order["order_status"],
        idempotency_key=order.get("idempotency_key"),
        created_at=order["created_at"],
        updated_at=order["updated_at"]
    )

# 6. Cancel Order (With Atomic Inventory Restoration)
@router.post("/orders/{order_id}/cancel", response_model=ShoppingOrderResponse)
async def cancel_shopping_order(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        obj_id = ObjectId(order_id)
        query = {"_id": obj_id}
    except Exception:
        query = {"_id": order_id}

    order = await db.shopping_orders.find_one(query)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order["customer_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this order")

    if order["order_status"] in ["shipped", "delivered", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order cannot be cancelled in its current state ('{order['order_status']}')."
        )

    # Atomically restore inventory for each item in the order
    for itm in order["items"]:
        await db.products.update_one(
            {"_id": itm["product_id"]},
            {"$inc": {"stock": itm["quantity"]}}
        )

    now = datetime.now(timezone.utc)
    await db.shopping_orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"order_status": "cancelled", "updated_at": now}}
    )

    await record_audit_event(
        event_type="ORDER_SECURITY_STATUS_CHANGED",
        raw_actor_id=current_user["id"],
        metadata={"order_id": str(order["_id"]), "old_status": order["order_status"], "new_status": "cancelled"}
    )

    # Trigger notification for customer confirming cancellation & stock release
    from app.services.notification_service import create_event_notification
    await create_event_notification(
        recipient_user_id=current_user["id"],
        actor_user_id=None,
        category="shopping",
        event_type="shopping_order_status",
        title=f"Order Cancelled: #{str(order['_id'])[-8:]}",
        desc="Your order was cancelled successfully and items have been released.",
        navigation_target=f"shopping:order:{str(order['_id'])}",
        metadata={"order_id": str(order["_id"]), "order_status": "cancelled"},
        event_id=f"shopping_order_cancelled_{str(order['_id'])}"
    )


    order["order_status"] = "cancelled"
    order["updated_at"] = now
    items = [ShoppingOrderItemSnapshot(**it) for it in order["items"]]

    return ShoppingOrderResponse(
        id=str(order["_id"]),
        customer_id=order["customer_id"],
        customer_name=order["customer_name"],
        customer_email=order["customer_email"],
        shipping_full_name=order["shipping_full_name"],
        shipping_phone=order["shipping_phone"],
        shipping_address=order["shipping_address"],
        shipping_city=order["shipping_city"],
        shipping_postal_code=order["shipping_postal_code"],
        items=items,
        total_items_count=order["total_items_count"],
        subtotal_paise=order["subtotal_paise"],
        shipping_paise=order["shipping_paise"],
        taxes_paise=order["taxes_paise"],
        discount_paise=order.get("discount_paise", 0),
        total_paise=order["total_paise"],
        total_inr=round(order["total_paise"] / 100, 2),
        payment_method=order["payment_method"],
        payment_status=order["payment_status"],
        order_status=order["order_status"],
        idempotency_key=order.get("idempotency_key"),
        created_at=order["created_at"],
        updated_at=order["updated_at"]
    )


# =======================================================================
# 6. SELLER OPERATIONS (Phase 4: Zaviro Merchant Portal)
# =======================================================================

@router.post("/seller/register", response_model=SellerResponse, status_code=status.HTTP_201_CREATED)
async def register_seller(
    payload: SellerRegisterPayload,
    current_user: dict = Depends(get_current_user)
):
    """Registers the authenticated user as a Zaviro Marketplace Seller with auditable onboarding."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    existing_seller = await db.sellers.find_one({"user_id": current_user["id"]})
    if existing_seller:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already registered as a seller."
        )

    now = datetime.now(timezone.utc)
    seller_doc = {
        "user_id": current_user["id"],
        "business_name": payload.business_name.strip(),
        "business_category": payload.business_category.strip(),
        "contact_phone": payload.contact_phone.strip(),
        "business_address": payload.business_address.strip(),
        "city": payload.city.strip(),
        "state": payload.state.strip(),
        "pincode": payload.pincode.strip(),
        "gstin_or_pan": payload.gstin_or_pan.strip() if payload.gstin_or_pan else None,
        "status": "approved",  # Standard auto-approved onboarding for verified authenticated users
        "created_at": now,
        "updated_at": now
    }

    insert_res = await db.sellers.insert_one(seller_doc)
    seller_id = str(insert_res.inserted_id)

    # Update user record with role 'seller'
    await db.users.update_one(
        {"_id": ObjectId(current_user["id"])},
        {"$addToSet": {"roles": "seller"}}
    )

    return SellerResponse(
        id=seller_id,
        user_id=seller_doc["user_id"],
        business_name=seller_doc["business_name"],
        business_category=seller_doc["business_category"],
        contact_phone=seller_doc["contact_phone"],
        business_address=seller_doc["business_address"],
        city=seller_doc["city"],
        state=seller_doc["state"],
        pincode=seller_doc["pincode"],
        gstin_or_pan=seller_doc["gstin_or_pan"],
        status=seller_doc["status"],
        created_at=seller_doc["created_at"],
        updated_at=seller_doc["updated_at"]
    )


@router.get("/seller/profile", response_model=SellerResponse)
async def get_seller_profile(
    current_user: dict = Depends(get_current_user)
):
    """Retrieves seller profile for current authenticated user."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    seller = await db.sellers.find_one({"user_id": current_user["id"]})
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller profile not found")

    return SellerResponse(
        id=str(seller["_id"]),
        user_id=seller["user_id"],
        business_name=seller["business_name"],
        business_category=seller["business_category"],
        contact_phone=seller["contact_phone"],
        business_address=seller["business_address"],
        city=seller["city"],
        state=seller["state"],
        pincode=seller["pincode"],
        gstin_or_pan=seller.get("gstin_or_pan"),
        status=seller["status"],
        created_at=seller["created_at"],
        updated_at=seller["updated_at"]
    )


@router.get("/seller/dashboard", response_model=SellerDashboardResponse)
async def get_seller_dashboard(
    current_user: dict = Depends(get_current_user)
):
    """Calculates live seller analytics, product metrics, and gross sales from real database records."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    seller = await db.sellers.find_one({"user_id": current_user["id"]})
    if not seller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Must be a registered seller")

    seller_id_str = current_user["id"]

    # Product metrics for this seller
    active_prods = await db.products.count_documents({
        "seller_id": seller_id_str,
        "is_published": True,
        "is_available": True
    })

    low_stock_prods = await db.products.count_documents({
        "seller_id": seller_id_str,
        "is_published": True,
        "stock": {"$lte": 5}
    })

    # Order metrics for this seller
    orders_cursor = db.shopping_orders.find({"items.seller_id": seller_id_str})
    pending_orders = 0
    fulfilled_orders = 0
    gross_sales_paise = 0

    async for ord_doc in orders_cursor:
        st = ord_doc.get("order_status")
        if st in ("placed", "confirmed", "processing"):
            pending_orders += 1
        elif st in ("shipped", "delivered"):
            fulfilled_orders += 1

        # Sum gross item sales for this seller's items (excluding cancelled)
        if st != "cancelled":
            for itm in ord_doc.get("items", []):
                if itm.get("seller_id") == seller_id_str:
                    gross_sales_paise += itm.get("total_price_paise", 0)

    return SellerDashboardResponse(
        seller_id=str(seller["_id"]),
        business_name=seller["business_name"],
        status=seller["status"],
        active_products=active_prods,
        low_stock_products=low_stock_prods,
        pending_orders=pending_orders,
        fulfilled_orders=fulfilled_orders,
        gross_sales_paise=gross_sales_paise,
        gross_sales_inr=round(gross_sales_paise / 100, 2)
    )


@router.get("/seller/products", response_model=List[ProductResponse])
async def list_seller_products(
    current_user: dict = Depends(get_current_user)
):
    """Lists all products owned by the authenticated seller."""
    db = get_database()
    if db is None:
        return []

    seller = await db.sellers.find_one({"user_id": current_user["id"]})
    if not seller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Must be a registered seller")

    cursor = db.products.find({"seller_id": current_user["id"]}).sort("created_at", -1)
    products = []
    async for p in cursor:
        price_p = p["price_paise"]
        mrp_p = p.get("mrp_paise")
        products.append(ProductResponse(
            id=str(p["_id"]),
            name=p["name"],
            brand=p.get("brand", "Generic"),
            sku=p.get("sku", ""),
            category=p.get("category", "General"),
            description=p.get("description", ""),
            price_paise=price_p,
            price_inr=round(price_p / 100, 2),
            mrp_paise=mrp_p,
            mrp_inr=round(mrp_p / 100, 2) if mrp_p else None,
            rating=p.get("rating", 5.0),
            reviews_count=p.get("reviews_count", 0),
            stock=p.get("stock", 0),
            is_available=p.get("is_available", True) and p.get("stock", 0) > 0,
            is_published=p.get("is_published", True),
            is_seed_data=p.get("is_seed_data", False),
            seller_id=p.get("seller_id"),
            seller_name=p.get("seller_name"),
            images=p.get("images", []),
            features=p.get("features", []),
            created_at=p.get("created_at", datetime.now(timezone.utc)),
            updated_at=p.get("updated_at", datetime.now(timezone.utc))
        ))
    return products


@router.post("/seller/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_seller_product(
    payload: ProductCreatePayload,
    current_user: dict = Depends(get_current_user)
):
    """Creates a new product catalog item under the authenticated seller's ownership."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    seller = await db.sellers.find_one({"user_id": current_user["id"]})
    if not seller or seller.get("status") != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only approved sellers can publish new products."
        )

    now = datetime.now(timezone.utc)
    sku = payload.sku.strip() if payload.sku else f"SKU-{int(now.timestamp())}-{current_user['id'][:4]}"

    product_id = f"prod_seller_{int(now.timestamp())}_{ObjectId()}"
    product_doc = {
        "_id": product_id,
        "name": payload.name.strip(),
        "brand": payload.brand.strip(),
        "category": payload.category.strip(),
        "description": payload.description.strip(),
        "price_paise": payload.price_paise,
        "mrp_paise": payload.mrp_paise or payload.price_paise,
        "stock": payload.stock,
        "sku": sku,
        "images": payload.images or ["https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600"],
        "features": payload.features or [],
        "rating": 5.0,
        "reviews_count": 0,
        "is_available": payload.is_available,
        "is_published": payload.is_published,
        "is_seed_data": False,
        "seller_id": current_user["id"],
        "seller_name": seller["business_name"],
        "created_at": now,
        "updated_at": now
    }

    await db.products.insert_one(product_doc)

    return ProductResponse(
        id=product_id,
        name=product_doc["name"],
        brand=product_doc["brand"],
        sku=product_doc["sku"],
        category=product_doc["category"],
        description=product_doc["description"],
        price_paise=product_doc["price_paise"],
        price_inr=round(product_doc["price_paise"] / 100, 2),
        mrp_paise=product_doc["mrp_paise"],
        mrp_inr=round(product_doc["mrp_paise"] / 100, 2) if product_doc["mrp_paise"] else None,
        rating=product_doc["rating"],
        reviews_count=product_doc["reviews_count"],
        stock=product_doc["stock"],
        is_available=product_doc["is_available"] and product_doc["stock"] > 0,
        is_published=product_doc["is_published"],
        is_seed_data=False,
        seller_id=product_doc["seller_id"],
        seller_name=product_doc["seller_name"],
        images=product_doc["images"],
        features=product_doc["features"],
        created_at=product_doc["created_at"],
        updated_at=product_doc["updated_at"]
    )


@router.patch("/seller/products/{product_id}", response_model=ProductResponse)
async def update_seller_product(
    product_id: str,
    payload: ProductUpdatePayload,
    current_user: dict = Depends(get_current_user)
):
    """Updates an existing product with strict seller ownership verification."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    existing = await db.products.find_one({"_id": product_id})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    if existing.get("seller_id") != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot modify products belonging to another seller."
        )

    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.brand is not None:
        updates["brand"] = payload.brand.strip()
    if payload.category is not None:
        updates["category"] = payload.category.strip()
    if payload.description is not None:
        updates["description"] = payload.description.strip()
    if payload.price_paise is not None:
        updates["price_paise"] = payload.price_paise
    if payload.mrp_paise is not None:
        updates["mrp_paise"] = payload.mrp_paise
    if payload.stock is not None:
        updates["stock"] = payload.stock
    if payload.images is not None:
        updates["images"] = payload.images
    if payload.features is not None:
        updates["features"] = payload.features
    if payload.is_available is not None:
        updates["is_available"] = payload.is_available
    if payload.is_published is not None:
        updates["is_published"] = payload.is_published

    now = datetime.now(timezone.utc)
    updates["updated_at"] = now

    await db.products.update_one({"_id": product_id}, {"$set": updates})
    updated_prod = await db.products.find_one({"_id": product_id})

    price_p = updated_prod["price_paise"]
    mrp_p = updated_prod.get("mrp_paise")

    return ProductResponse(
        id=str(updated_prod["_id"]),
        name=updated_prod["name"],
        brand=updated_prod.get("brand", "Generic"),
        sku=updated_prod.get("sku", ""),
        category=updated_prod.get("category", "General"),
        description=updated_prod.get("description", ""),
        price_paise=price_p,
        price_inr=round(price_p / 100, 2),
        mrp_paise=mrp_p,
        mrp_inr=round(mrp_p / 100, 2) if mrp_p else None,
        rating=updated_prod.get("rating", 5.0),
        reviews_count=updated_prod.get("reviews_count", 0),
        stock=updated_prod.get("stock", 0),
        is_available=updated_prod.get("is_available", True) and updated_prod.get("stock", 0) > 0,
        is_published=updated_prod.get("is_published", True),
        is_seed_data=updated_prod.get("is_seed_data", False),
        seller_id=updated_prod.get("seller_id"),
        seller_name=updated_prod.get("seller_name"),
        images=updated_prod.get("images", []),
        features=updated_prod.get("features", []),
        created_at=updated_prod.get("created_at", now),
        updated_at=updated_prod.get("updated_at", now)
    )


@router.delete("/seller/products/{product_id}")
async def delete_seller_product(
    product_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Deletes/unpublishes a product owned by the authenticated seller."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    existing = await db.products.find_one({"_id": product_id})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    if existing.get("seller_id") != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot delete products belonging to another seller."
        )

    # Soft delete / unpublish
    await db.products.update_one(
        {"_id": product_id},
        {"$set": {"is_published": False, "is_available": False, "updated_at": datetime.now(timezone.utc)}}
    )
    return {"status": "deleted", "product_id": product_id}


@router.get("/seller/orders", response_model=List[ShoppingOrderResponse])
async def list_seller_orders(
    current_user: dict = Depends(get_current_user)
):
    """Lists orders that contain products belonging to the authenticated seller."""
    db = get_database()
    if db is None:
        return []

    seller = await db.sellers.find_one({"user_id": current_user["id"]})
    if not seller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Must be a registered seller")

    cursor = db.shopping_orders.find({"items.seller_id": current_user["id"]}).sort("created_at", -1)
    orders = []
    async for ord_doc in cursor:
        items = [ShoppingOrderItemSnapshot(**it) for it in ord_doc["items"]]
        orders.append(ShoppingOrderResponse(
            id=str(ord_doc["_id"]),
            customer_id=ord_doc["customer_id"],
            customer_name=ord_doc["customer_name"],
            customer_email=ord_doc["customer_email"],
            shipping_full_name=ord_doc["shipping_full_name"],
            shipping_phone=ord_doc["shipping_phone"],
            shipping_address=ord_doc["shipping_address"],
            shipping_city=ord_doc["shipping_city"],
            shipping_postal_code=ord_doc["shipping_postal_code"],
            items=items,
            total_items_count=ord_doc["total_items_count"],
            subtotal_paise=ord_doc["subtotal_paise"],
            shipping_paise=ord_doc["shipping_paise"],
            taxes_paise=ord_doc["taxes_paise"],
            discount_paise=ord_doc.get("discount_paise", 0),
            total_paise=ord_doc["total_paise"],
            total_inr=round(ord_doc["total_paise"] / 100, 2),
            payment_method=ord_doc["payment_method"],
            payment_status=ord_doc["payment_status"],
            order_status=ord_doc["order_status"],
            idempotency_key=ord_doc.get("idempotency_key"),
            created_at=ord_doc["created_at"],
            updated_at=ord_doc["updated_at"]
        ))
    return orders


@router.patch("/seller/orders/{order_id}/status", response_model=ShoppingOrderResponse)
async def update_seller_order_status(
    order_id: str,
    payload: SellerOrderStatusUpdatePayload,
    current_user: dict = Depends(get_current_user)
):
    """Transitions seller order status through valid transitions: processing -> shipped -> delivered."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        order_obj = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order ID")

    order = await db.shopping_orders.find_one({"_id": order_obj})
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    # Verify order contains at least one item from this seller
    has_seller_item = any(it.get("seller_id") == current_user["id"] for it in order["items"])
    if not has_seller_item:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: This order does not contain products belonging to you."
        )

    current_status = order["order_status"]
    new_status = payload.status

    # Validate permissible state transitions
    valid_transitions = {
        "placed": ["confirmed", "processing"],
        "confirmed": ["processing"],
        "processing": ["shipped"],
        "shipped": ["delivered"],
        "delivered": [],
        "cancelled": []
    }

    if new_status not in valid_transitions.get(current_status, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid order status transition from '{current_status}' to '{new_status}'."
        )

    now = datetime.now(timezone.utc)
    await db.shopping_orders.update_one(
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
        category="shopping",
        event_type="shopping_order_status",
        title=f"Order Update: #{str(order['_id'])[-8:]} is now {new_status.capitalize()}",
        desc=f"Your package status was updated to {new_status} by the merchant.",
        navigation_target=f"shopping:order:{str(order['_id'])}",
        metadata={"order_id": str(order["_id"]), "order_status": new_status},
        event_id=f"shopping_order_{new_status}_{str(order['_id'])}"
    )

    items = [ShoppingOrderItemSnapshot(**it) for it in order["items"]]
    return ShoppingOrderResponse(
        id=str(order["_id"]),
        customer_id=order["customer_id"],
        customer_name=order["customer_name"],
        customer_email=order["customer_email"],
        shipping_full_name=order["shipping_full_name"],
        shipping_phone=order["shipping_phone"],
        shipping_address=order["shipping_address"],
        shipping_city=order["shipping_city"],
        shipping_postal_code=order["shipping_postal_code"],
        items=items,
        total_items_count=order["total_items_count"],
        subtotal_paise=order["subtotal_paise"],
        shipping_paise=order["shipping_paise"],
        taxes_paise=order["taxes_paise"],
        discount_paise=order.get("discount_paise", 0),
        total_paise=order["total_paise"],
        total_inr=round(order["total_paise"] / 100, 2),
        payment_method=order["payment_method"],
        payment_status=order["payment_status"],
        order_status=order["order_status"],
        idempotency_key=order.get("idempotency_key"),
        created_at=order["created_at"],
        updated_at=order["updated_at"]
    )

