import pymongo

client = pymongo.MongoClient("mongodb://127.0.0.1:27017")
db = client["super_ai_db"]

# Fix chat_rooms
for r in db.chat_rooms.find():
    lm = r.get("last_message")
    if lm and "id" not in lm:
        lm["id"] = "synth_msg_001"
        db.chat_rooms.update_one({"_id": r["_id"]}, {"$set": {"last_message": lm}})

# Fix bank_accounts
for a in db.bank_accounts.find():
    masked = a.get("account_number_masked") or "XXXX-9012"
    db.bank_accounts.update_one({"_id": a["_id"]}, {"$set": {"masked_account_number": masked}})

print("Data fields updated successfully.")
