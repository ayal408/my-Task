$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .env)) {
    $secret = [Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N")
    Set-Content -Path .env -Value "DB_PASSWORD=$secret" -Encoding ascii
}
# Export only public NetFree certificates; private keys are never exported.
$certs = @(Get-ChildItem Cert:\CurrentUser\Root, Cert:\LocalMachine\Root, Cert:\CurrentUser\CA, Cert:\LocalMachine\CA |
    Where-Object { $_.Subject -match "NetFree" } |
    Sort-Object Thumbprint -Unique)
foreach ($folder in @("server/certs", "client/certs")) {
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $certPath = Join-Path $folder "netfree.crt"
    if ($certs.Count -gt 0) {
        $pem = ($certs | ForEach-Object {
            "-----BEGIN CERTIFICATE-----`n" +
            [Convert]::ToBase64String($_.RawData, [Base64FormattingOptions]::InsertLineBreaks) +
            "`n-----END CERTIFICATE-----`n"
        }) -join "`n"
        [IO.File]::WriteAllText((Join-Path $PSScriptRoot $certPath), $pem, [Text.Encoding]::ASCII)
    }
}
if ($certs.Count -gt 0) { Write-Host "NetFree certificates configured for Python and Node builds." }
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "Docker build failed. See the first ERROR/SSL message above. For certificate errors, check the NetFree certificates in Windows or server/certs and client/certs." }
Write-Host "Open http://localhost:8095"
Start-Process "http://localhost:8095"
