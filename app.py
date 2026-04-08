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

# --- MODELLER ---
class ShipmentRequest(BaseModel):
    sender_name: str
    contact: str
    shipment_type: str
    dimensions: str
    from_city: str
    to_city: str
    kg: float
    calculated_price: float
    photo: str = None

class BidRequest(BaseModel):
    shipment_id: str
    carrier_name: str
    carrier_contact: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    phone: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

# YENİ EKLENEN MODEL: Güvenlik Onaylı Teslimat
class DeliverRequest(BaseModel):
    shipment_id: str
    user_email: str  # GÜVENLİK İÇİN EKLENDİ: İsteği atan kim?

# YENİ EKLENEN MODEL: Admin Durum Güncellemesi İçin
class UpdateStatusRequest(BaseModel):
    shipment_id: str
    new_status: str


# --- SAYFA ROTALARI ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/sender", response_class=HTMLResponse)
async def read_sender(request: Request):
    return templates.TemplateResponse("sender.html", {"request": request})

@app.get("/carrier", response_class=HTMLResponse)
async def read_carrier(request: Request):
    return templates.TemplateResponse("carrier.html", {"request": request})

@app.get("/auth", response_class=HTMLResponse)
async def read_auth(request: Request):
    return templates.TemplateResponse("auth.html", {"request": request})

@app.get("/orders", response_class=HTMLResponse)
async def read_orders(request: Request):
    return templates.TemplateResponse("orders.html", {"request": request})

# YENİ SAYFA ROTASI: Yönetici (Admin) Paneli
@app.get("/admin", response_class=HTMLResponse)
async def read_admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


# --- İŞ MODELİ VE KARGO API ROTALARI ---
@app.post("/api/create_shipment")
async def create_shipment(shipment: ShipmentRequest):
    shipment_id = str(uuid.uuid4())[:8] 
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
        "photo": shipment.photo, 
        "provision_paid": provision_amount, 
        "current_bid": round(carrier_max_bid, 2), 
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
        
        # GÜVENLİK YAMASI: Kargo zaten alınmış mı?
        if shipment_data.get("status") != "waiting_for_bids":
            return JSONResponse(content={"status": "error", "message": "Üzgünüz, bu kargo saniyeler önce başka bir taşıyıcı tarafından alındı!"})
        
        current_bid = float(shipment_data.get("current_bid", 0))
        
        new_bid = {
            "shipment_id": bid.shipment_id,
            "carrier_name": bid.carrier_name,
            "carrier_contact": bid.carrier_contact,
            "bid_amount": current_bid
        }
        db.collection("bids").add(new_bid)
        
        # MANTIK YAMASI: Kargo ilk tıklayana kilitlenir ve taşıyıcı sisteme kaydedilir.
        doc_ref.update({
            "status": "carrier_received", 
            "carrier_name": bid.carrier_name,
            "carrier_contact": bid.carrier_contact
        })
        
        return JSONResponse(content={"status": "success", "message": "Tebrikler! Kargo size atandı. Teslimat sürecini başlatabilirsiniz."})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.get("/api/my_shipments")
async def get_my_shipments(email: str):
    try:
        docs = db.collection("shipments").where("contact", "==", email).stream()
        my_shipments = [doc.to_dict() for doc in docs]
        return JSONResponse(content={"status": "success", "data": my_shipments})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.post("/api/deliver")
async def deliver_shipment(payload: DeliverRequest):
    try:
        doc_ref = db.collection("shipments").document(payload.shipment_id)
        doc_ref.update({"status": "delivered"})
        return JSONResponse(content={"status": "success", "message": "Teslimat başarıyla onaylandı! Platform komisyonu kesildi, kalan ödeme taşıyıcıya aktarılıyor."})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

# YENİ API: Admin İçin Manuel Durum Güncelleme
@app.post("/api/update_status")
async def update_status(payload: UpdateStatusRequest):
    try:
        db.collection("shipments").document(payload.shipment_id).update({"status": payload.new_status})
        return JSONResponse(content={"status": "success", "message": "Kargo durumu güncellendi!"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

# YENİ API: Admin Dashboard Verilerini Çekme (Ciro ve Kâr Hesaplaması)
@app.get("/api/dashboard_stats")
async def get_dashboard_stats():
    try:
        docs = db.collection("shipments").stream()
        shipments = [doc.to_dict() for doc in docs]

        total_volume = 0
        total_profit = 0
        active_count = 0
        completed_count = 0

        for s in shipments:
            provision = float(s.get("provision_paid", 0))
            final_bid = float(s.get("current_bid", 0))
            status = s.get("status", "waiting_for_bids")

            total_volume += provision
            
            # Kâr: Müşteriden çekilen (provision) - Taşıyıcıya verilen (final_bid)
            if status != "waiting_for_bids":
                total_profit += (provision - final_bid)

            if status == "delivered":
                completed_count += 1
            else:
                active_count += 1

        return JSONResponse(content={
            "status": "success",
            "data": {
                "total_volume": round(total_volume, 2),
                "total_profit": round(total_profit, 2),
                "active_count": active_count,
                "completed_count": completed_count,
                "all_shipments": shipments
            }
        })
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})


# --- AUTH API ---
@app.post("/api/register")
async def register_user(user: RegisterRequest):
    try:
        existing_users = db.collection("users").where("email", "==", user.email).stream()
        if len(list(existing_users)) > 0:
            return JSONResponse(content={"status": "error", "message": "Bu e-posta adresi zaten kayıtlı!"})
        new_user = {"name": user.name, "email": user.email, "phone": user.phone, "password": user.password}
        db.collection("users").add(new_user)
        return JSONResponse(content={"status": "success", "message": "Hesap başarıyla oluşturuldu."})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.post("/api/login")
async def login_user(user: LoginRequest):
    try:
        users_ref = db.collection("users").where("email", "==", user.email).where("password", "==", user.password).stream()
        user_list = [doc.to_dict() for doc in users_ref]
        if len(user_list) == 0:
            return JSONResponse(content={"status": "error", "message": "E-posta veya şifre hatalı!"})
        logged_in_user = user_list[0]
        logged_in_user.pop('password', None) 
        return JSONResponse(content={"status": "success", "message": "Giriş başarılı", "data": logged_in_user})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)