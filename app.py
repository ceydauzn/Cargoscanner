from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import uuid
import firebase_admin
from firebase_admin import credentials, firestore

# --- FIREBASE BAĞLANTISI ---
try:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("🔥 Firebase bağlantısı BAŞARILI!")
except Exception as e:
    print(f"❌ Firebase bağlantı hatası: {e}")

app = FastAPI(title="BaggageMatch API")
templates = Jinja2Templates(directory="templates")

# --- VERİ MODELLERİ (Gelen verilerin kuralları) ---
class ShipmentRequest(BaseModel):
    sender_name: str
    contact: str
    from_city: str
    to_city: str
    kg: float
    calculated_price: float

class BidRequest(BaseModel):
    shipment_id: str
    carrier_name: str
    carrier_contact: str

# --- 1. VİTRİN: Gönderici Sayfası ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --- 2. API: İhale Başlatma (Gönderici) ---
@app.post("/api/create_shipment")
async def create_shipment(shipment: ShipmentRequest):
    shipment_id = str(uuid.uuid4())[:8] 
    
    new_shipment = {
        "shipment_id": shipment_id,
        "sender_name": shipment.sender_name,
        "contact": shipment.contact,
        "route": f"{shipment.from_city} -> {shipment.to_city}",
        "kg": shipment.kg,
        "base_price": shipment.calculated_price,
        "current_bid": shipment.calculated_price, # İhale fiyatı buradan başlıyor
        "status": "waiting_for_bids"
    }
    
    db.collection("shipments").document(shipment_id).set(new_shipment)
    
    return JSONResponse(content={
        "status": "success",
        "message": "Provizyon alındı, ihale taşıyıcılara bildirildi!",
        "data": new_shipment
    })

# --- 3. API: Bekleyen Kargoları Listeleme (Taşıyıcı İçin) ---
@app.get("/api/shipments")
async def get_shipments():
    try:
        # Sadece "teklif bekleyen" kargoları bul ve getir
        docs = db.collection("shipments").where("status", "==", "waiting_for_bids").stream()
        shipments_list = [doc.to_dict() for doc in docs]
        
        return JSONResponse(content={"status": "success", "data": shipments_list})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

# --- 4. API: Teklif Verme ve Fiyat Düşürme (Ters İhale) ---
@app.post("/api/place_bid")
async def place_bid(bid: BidRequest):
    try:
        # Kargo dosyasını bul
        doc_ref = db.collection("shipments").document(bid.shipment_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return JSONResponse(content={"status": "error", "message": "Kargo bulunamadı!"})
            
        shipment_data = doc.to_dict()
        current_bid = float(shipment_data.get("current_bid", 0))
        
        # 1. Hamle: Taşıyıcının teklifini "bids" koleksiyonuna kaydet
        new_bid = {
            "shipment_id": bid.shipment_id,
            "carrier_name": bid.carrier_name,
            "carrier_contact": bid.carrier_contact,
            "bid_amount": current_bid # O anki güncel fiyat üzerinden kabul etti
        }
        db.collection("bids").add(new_bid)
        
        # 2. Hamle (TERS İHALE): Kargonun fiyatını 1 Dolar düşür!
        new_price = current_bid - 1.0
        doc_ref.update({"current_bid": new_price})
        
        return JSONResponse(content={
            "status": "success", 
            "message": f"Teklif başarılı! Kargonun yeni ihale fiyatı: ${new_price}",
            "new_price": new_price
        })
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)