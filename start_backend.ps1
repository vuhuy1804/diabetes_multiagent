
# start_backend.ps1
# Khoi dong Backend Flask voi CA certificate tu certifi

$ErrorActionPreference = "Stop"

# Di chuyen den thu muc goc project
Set-Location $PSScriptRoot

# Python trong .venv hien tai
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Khong tim thay Python trong .venv"
}

# Tu dong lay duong dan CA certificate
$certFile = (& $python -c "import certifi; print(certifi.where())").Trim()

if (-not (Test-Path $certFile)) {
    throw "Khong tim thay CA certificate"
}

# Thiet lap SSL truoc khi khoi dong Flask
$env:SSL_CERT_FILE = $certFile

Write-Host "SSL certificate: $certFile"
Write-Host ""

# Kiem tra Neo4j
Write-Host "Checking Neo4j connection..."
& $python backend/scripts/neo4j_cli.py check

# Khoi dong Flask
Write-Host ""
Write-Host "Starting Flask Backend..."
& $python backend/app.py
