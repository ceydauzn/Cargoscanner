from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import uuid

app = FastAPI(title="BaggageMatch API")
templates = Jinja2Templates(directory="templates")

# İleride Firebase'e bağlanacak olan geçici veritabanımız (Memory DB)
db_shipments = []

# API için Veri Modeli (Gelen verinin doğruluğunu kontrol eder)
class ShipmentRequest(BaseModel):
    sender_name: str
    from_city: str
    to_city: str
    kg: float
    calculated_price: float

# 1. VİTRİN: Web sayfamızı gösteren ana rota
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 2. API: İhaleyi Başlatan Arka Kapı (Frontend buraya veri gönderecek)
@app.post("/api/create_shipment")
async def create_shipment(shipment: ShipmentRequest):
    # Yeni bir gönderi (ihale) belgesi oluşturuyoruz (Firebase mantığı)
    new_shipment = {
        "shipment_id": str(uuid.uuid4())[:8], # Rastgele 8 haneli ID
        "sender_name": shipment.sender_name,
        "route": f"{shipment.from_city} -> {shipment.to_city}",
        "kg": shipment.kg,
        "base_price": shipment.calculated_price, # Müşteriden çekilen provizyon
        "current_bid": shipment.calculated_price, # İhale bu fiyattan başlıyor
        "status": "waiting_for_bids"
    }
    
    # Veritabanına (şimdilik listeye) kaydet
    db_shipments.append(new_shipment)
    print(f"YENİ İHALE BAŞLADI: {new_shipment}")
    
    # Mobil uygulamaya veya frontend'e "Başarılı" yanıtı dön
    return JSONResponse(content={
        "status": "success",
        "message": "Provizyon alındı, ihale taşıyıcılara bildirildi!",
        "data": new_shipment
    })

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)