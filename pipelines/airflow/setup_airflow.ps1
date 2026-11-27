# Run from the repository root: powershell -ExecutionPolicy Bypass -File .\pipelines\airflow\setup_airflow.ps1
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$airflowDir = $PSScriptRoot
if (-not (Test-Path (Join-Path $projectRoot 'dvc.lock'))) {
    throw 'Run from the MLOps repository with the Phase 3 dvc.lock available.'
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is not installed. Install and start Docker Desktop with WSL2/Linux containers.'
}
docker compose version
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose plugin is not working.' }
docker info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker engine is not running. Start Docker Desktop.' }
foreach ($folder in @('dags', 'logs', 'plugins', 'config')) {
    New-Item -Force -ItemType Directory (Join-Path $airflowDir $folder) | Out-Null
}
$compose = Join-Path $airflowDir 'docker-compose.yaml'
if (-not (Test-Path $compose)) {
    $url = 'https://airflow.apache.org/docs/apache-airflow/3.4.0/docker-compose.yaml'
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $compose
    Write-Host 'Downloaded matching official Airflow 3.4.0 Compose file.'
} else {
    Write-Host 'Existing docker-compose.yaml preserved (not overwritten).'
}
$dotenv = Join-Path $airflowDir '.env'
if (-not (Test-Path $dotenv)) {
    @('AIRFLOW_UID=50000', 'AIRFLOW_IMAGE_NAME=apache/airflow:3.4.0') |
        Set-Content -Path $dotenv -Encoding ascii
}
$gitignore = Join-Path $projectRoot '.gitignore'
$ignoreLines = @('/pipelines/airflow/logs/', '/pipelines/airflow/config/', '/pipelines/airflow/plugins/', '/pipelines/airflow/.env')
foreach ($line in $ignoreLines) {
    if (-not (Select-String -LiteralPath $gitignore -Pattern $line -SimpleMatch -Quiet)) {
        Add-Content -LiteralPath $gitignore -Value $line
    }
}
$attrs = Join-Path $projectRoot '.gitattributes'
if (-not (Test-Path $attrs)) { New-Item -ItemType File $attrs | Out-Null }
if (-not (Select-String -LiteralPath $attrs -Pattern '*.sh text eol=lf' -SimpleMatch -Quiet)) {
    Add-Content -LiteralPath $attrs -Value '*.sh text eol=lf'
}
Push-Location $airflowDir
try {
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed' }
} finally { Pop-Location }
Write-Host 'PHASE 4 AIRFLOW COMPOSE CONFIG VALID. Next: start/init Docker stack.'
