<#
 Runs `python manage.py <args>` against the PRODUCTION database (Supabase) from your PC, with production settings.
 Needs backend\.env.production (copy backend\.env.production.example). Uses DIRECT_URL (session pooler, port 5432).

 Examples (from the project root, venv active):
   .\scripts\prod-manage.ps1 migrate
   .\scripts\prod-manage.ps1 check_rls
   .\scripts\prod-manage.ps1 createsuperuser
   .\scripts\prod-manage.ps1 bootstrap_school_defaults
#>
param(
  [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)][string[]]$ManageArgs,
  [string]$EnvFile = "backend\.env.production"
)
$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root $EnvFile
if (-not (Test-Path $envPath)) { throw "Missing $envPath. Copy backend\.env.production.example to backend\.env.production and fill it in." }

foreach ($line in Get-Content $envPath) {
  if ($line -match '^\s*#' -or $line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { continue }
  $value = $Matches[2].Trim()
  if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) { $value = $value.Substring(1, $value.Length - 2) }
  Set-Item -Path "Env:$($Matches[1])" -Value $value
}
if (-not $env:DIRECT_URL) { throw "DIRECT_URL is empty in $EnvFile." }
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
$env:DJANGO_USE_DIRECT_URL = "1"

$dbHost = ($env:DIRECT_URL -replace '^.*@', '') -replace '[/?].*$', ''
Write-Host "About to run 'manage.py $ManageArgs' on the PRODUCTION database at $dbHost" -ForegroundColor Yellow
if ((Read-Host "Type YES to continue") -ne "YES") { Write-Host "Cancelled."; exit 1 }

Push-Location (Join-Path $root "backend")
try { python manage.py @ManageArgs; exit $LASTEXITCODE } finally { Pop-Location }
