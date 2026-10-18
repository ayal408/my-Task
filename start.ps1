$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .env)) {
    $secret = [Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N")
    Set-Content -Path .env -Value "DB_PASSWORD=$secret" -Encoding ascii
}
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "Docker build failed. Check that Docker Desktop is running." }
Write-Host "Open http://localhost:8095"
Start-Process "http://localhost:8095"
