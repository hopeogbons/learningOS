# Connected localhost launcher; preserve private settings and all user data.
param([ValidateSet('init','doctor','start','stop')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
switch ($Action) {
    'init' {
        Invoke-Docker compose -f deploy/compose.connected-local.yml --profile init run --build --rm --no-deps init
    }
    'doctor' {
        Invoke-Docker compose -f deploy/compose.connected-local.yml ps -a
        Invoke-Docker compose -f deploy/compose.connected-local.yml --profile diagnose run --build --rm --no-deps diagnose
    }
    'start' {
        if (-not (Test-Path '.runtime/localhost/localhost.env')) {
            Invoke-Docker compose -f deploy/compose.connected-local.yml --profile init run --build --rm --no-deps init
            Write-Host 'Fill .runtime/localhost/localhost.env privately, then run scripts/local.ps1 -Action start again.'
            exit 1
        }
        Invoke-Docker compose -f deploy/compose.connected-local.yml --profile diagnose run --build --rm --no-deps diagnose
        Invoke-Docker compose -f deploy/compose.demo.yml down
        Invoke-Docker compose -f deploy/compose.connected-local.yml up --build -d --wait
        Write-Host 'Connected app started with your configured browser origin. No sample data was seeded.'
    }
    'stop' { Invoke-Docker compose -f deploy/compose.connected-local.yml down }
}
