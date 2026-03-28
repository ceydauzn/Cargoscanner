# Python'un hafif bir versiyonunu kullanıyoruz
FROM python:3.9-slim

# Çalışma dizinini belirliyoruz
WORKDIR /app

# Gereksinimleri kopyalayıp kuruyoruz
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodlarını kopyalıyoruz
COPY . .

# Hugging Face Spaces portu
EXPOSE 7860

# FastAPI'yi uvicorn ile başlatıyoruz
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]