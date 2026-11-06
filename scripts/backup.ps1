<#
 Manual PostgreSQL backup (Supabase free tier has no managed backups).
 Needs the PostgreSQL client tools (pg_dump) on PATH:  winget install PostgreSQL.PostgreSQL  (or the EDB installer).
 Use the SESSION pooler / direct connection string (port 5432), not the 6543 transaction pooler.

 Usage:   .\scripts\backup.ps1 -Url "postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres"
 Or set:  $env:DIRECT_URL = "..."; .\scripts\backup.ps1
 Restore: pg_restore --no-owner --no-privileges --clean --if-exists -d "<target url>" .\backups\<file>.dump
#>
param(
  [string]$Url = $env:DIRECT_URL,
  [string]$OutDir = "backups"
)
if (-not $Url) { throw "Provide -Url or set DIRECT_URL (session pooler connection string)." }
if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) { throw "pg_dump was not found. Install the PostgreSQL client tools first." }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$file = Join-Path $OutDir ("school-saas-{0:yyyyMMdd-HHmm}.dump" -f (Get-Date))
pg_dump --format=custom --no-owner --no-privileges --file $file $Url
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed (exit code $LASTEXITCODE)." }
Write-Host ("Backup written to {0} ({1:N1} MB)" -f $file, ((Get-Item $file).Length / 1MB))
