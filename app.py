from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import uuid
import firebase_admin
from firebase_admin import credentials, firestore

try:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"❌ Firebase bağlantı hatası: {e}")

app = FastAPI(title="Cargo Scanner API")
templates = Jinja2Templates(directory="templates")

# Güncellenmiş Veri Modeli
class ShipmentRequest(BaseModel):
    sender_name: str
    contact: str
    shipment_type: str  # 'extra_baggage' veya 'cargo_only'
    dimensions: str
    from_city: str
    to_city: str
    kg: float
    calculated_price: float

class BidRequest(BaseModel):
    shipment_id: str
    carrier_name: str
    carrier_contact: str

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/sender", response_class=HTMLResponse)
async def read_sender(request: Request):
    return templates.TemplateResponse("sender.html", {"request": request})

@app.get("/carrier", response_class=HTMLResponse)
async def read_carrier(request: Request):
    return templates.TemplateResponse("carrier.html", {"request": request})

@app.post("/api/create_shipment")
async def create_shipment(shipment: ShipmentRequest):
    shipment_id = str(uuid.uuid4())[:8] 
    
    # İŞ MODELİ: %15 Komisyon Kesintisi
    provision_amount = shipment.calculated_price
    platform_commission = provision_amount * 0.15
    carrier_max_bid = provision_amount - platform_commission 
    
    new_shipment = {
        "shipment_id": shipment_id,
        "sender_name": shipment.sender_name,
        "contact": shipment.contact,
        "type": "Numune/Kargo" if shipment.shipment_type == "cargo_only" else "Bagaj Fazlası",
        "dimensions": shipment.dimensions,
        "route": f"{shipment.from_city} -> {shipment.to_city}",
        "kg": shipment.kg,
        "provision_paid": provision_amount, # Müşteriden çekilen asıl para (Örn: 35$)
        "current_bid": round(carrier_max_bid, 2), # Taşıyıcıların gördüğü ihale başlangıç rakamı (Örn: 29.75$)
        "status": "waiting_for_bids"
    }
    
    db.collection("shipments").document(shipment_id).set(new_shipment)
    return JSONResponse(content={"status": "success", "message": "Provizyon alındı! Taşıyıcılara bildirim gönderildi.", "data": new_shipment})

@app.get("/api/shipments")
async def get_shipments():
    try:
        docs = db.collection("shipments").where("status", "==", "waiting_for_bids").stream()
        shipments_list = [doc.to_dict() for doc in docs]
        return JSONResponse(content={"status": "success", "data": shipments_list})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.post("/api/place_bid")
async def place_bid(bid: BidRequest):
    try:
        doc_ref = db.collection("shipments").document(bid.shipment_id)
        doc = doc_ref.get()
        if not doc.exists:
            return JSONResponse(content={"status": "error", "message": "Kargo bulunamadı!"})
            
        shipment_data = doc.to_dict()
        current_bid = float(shipment_data.get("current_bid", 0))
        
        new_bid = {
            "shipment_id": bid.shipment_id,
            "carrier_name": bid.carrier_name,
            "carrier_contact": bid.carrier_contact,
            "bid_amount": current_bid
        }
        db.collection("bids").add(new_bid)
        
        # TERS İHALE: Her teklifte fiyat 1 dolar düşer (Aradaki fark sisteme kar yazar)
        new_price = round(current_bid - 1.0, 2)
        doc_ref.update({"current_bid": new_price})
        
        return JSONResponse(content={"status": "success", "message": f"Teklif başarılı! Yeni fiyat: ${new_price}", "new_price": new_price})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)