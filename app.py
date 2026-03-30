from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import uuid
import firebase_admin
from firebase_admin import credentials, firestore

# --- FIREBASE BAĞLANTISI ---
# İndirdiğin JSON dosyasının adının tam olarak "firebase_key.json" olduğundan emin ol.
try:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("🔥 Firebase bağlantısı BAŞARILI!")
except Exception as e:
    print(f"❌ Firebase bağlantı hatası: {e}")

app = FastAPI(title="BaggageMatch API")
templates = Jinja2Templates(directory="templates")

# API için Veri Modeli
class ShipmentRequest(BaseModel):
    sender_name: str
    contact: str
    from_city: str
    to_city: str
    kg: float
    calculated_price: float

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/create_shipment")
async def create_shipment(shipment: ShipmentRequest):
    shipment_id = str(uuid.uuid4())[:8] # Rastgele 8 haneli ID
    
    new_shipment = {
        "shipment_id": shipment_id,
        "sender_name": shipment.sender_name,
        "contact": shipment.contact,
        "route": f"{shipment.from_city} -> {shipment.to_city}",
        "kg": shipment.kg,
        "base_price": shipment.calculated_price,
        "current_bid": shipment.calculated_price,
        "status": "waiting_for_bids"
    }
    
    # Veriyi Firebase Firestore'daki "shipments" koleksiyonuna yazıyoruz!
    db.collection("shipments").document(shipment_id).set(new_shipment)
    print(f"✅ YENİ İHALE FIREBASE'E KAYDEDİLDİ: {new_shipment}")
    
    return JSONResponse(content={
        "status": "success",
        "message": "Provizyon alındı, ihale taşıyıcılara bildirildi!",
        "data": new_shipment
    })

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)