from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Form verilerini geçici olarak burada tutacağız (İleride bir DB'ye bağlarız)
waitlist = []

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "message": ""})

@app.post("/submit", response_class=HTMLResponse)
async def submit_form(
    request: Request, 
    user_type: str = Form(...), 
    name: str = Form(...), 
    contact: str = Form(...)
):
    # Gelen veriyi listeye ekliyoruz
    waitlist.append({"type": user_type, "name": name, "contact": contact})
    print(f"Yeni Kayıt: {user_type} - {name} - {contact}")
    
    success_msg = "Harika! Talebin alındı, en kısa sürede eşleşme için sana ulaşacağız."
    return templates.TemplateResponse("index.html", {"request": request, "message": success_msg})

if __name__ == "__main__":
    # Hugging Face Spaces için 7860 portu zorunludur
    uvicorn.run(app, host="0.0.0.0", port=7860)