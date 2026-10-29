# Skrip peluncuran pengembangan Collective Campus (Fase 7I)
# Mengompilasi Tailwind CSS terlebih dahulu, kemudian menjalankan server Django

$ErrorActionPreference = "Stop"

Write-Host "Membangun aset CSS (Tailwind CSS)..." -ForegroundColor Cyan
npm run build:css

if ($LASTEXITCODE -ne 0) {
    Write-Host "Kompilasi CSS gagal!" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Menjalankan Django dev server di http://127.0.0.1:8000/..." -ForegroundColor Green
& .venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
