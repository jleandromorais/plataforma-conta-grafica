# Script PowerShell para reiniciar Docker Compose
param([switch]$Force)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   PLATAFORMA CONTA GRAFICA - REINICIALIZACAO            " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# Parar containers
Write-Host "Parando containers..." -ForegroundColor Yellow
docker compose down -v 2>&1

# Aguardar um pouco
Start-Sleep -Seconds 3

# Subir containers
Write-Host "`nSubindo containers..." -ForegroundColor Yellow
docker compose up -d 2>&1

# Aguardar inicializacao
Write-Host "`nAguardando inicializacao (30 segundos)..." -ForegroundColor Cyan
Start-Sleep -Seconds 30

# Verificar status
Write-Host "`nStatus dos containers:" -ForegroundColor Cyan
docker compose ps 2>&1

Write-Host "`nReinicializacao concluida!" -ForegroundColor Green
Write-Host "Acesse Airflow em: http://localhost:8080" -ForegroundColor Green
