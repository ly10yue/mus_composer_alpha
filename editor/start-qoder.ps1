param(
    [string]$BridgeDirectory = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Qoder-Bridge-main'),
    [ValidateSet('qoder-deepseek-flash','qoder-deepseek-pro')][string]$Model = 'qoder-deepseek-flash',
    [ValidateRange(1,65535)][int]$Port = 8646,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path $PSScriptRoot -Parent
$editorExe = Join-Path $projectDirectory 'dist\editor-0.12.0\IntervalComposer\IntervalComposer.exe'
$bridgeKeyPath = Join-Path $BridgeDirectory '.runtime\bridge-key'
$baseUrl = "http://127.0.0.1:$Port/v1"
if (!(Test-Path -LiteralPath $editorExe -PathType Leaf)) { throw 'Editor executable not found. Build editor-0.12.0 first.' }
if (!(Test-Path -LiteralPath $bridgeKeyPath -PathType Leaf)) { throw 'Bridge key file not found. Use -BridgeDirectory to select the installed Bridge folder.' }
$bridgeKey = [IO.File]::ReadAllText($bridgeKeyPath).Trim()
if ([string]::IsNullOrWhiteSpace($bridgeKey) -or $bridgeKey.Contains("`r") -or $bridgeKey.Contains("`n")) { throw 'Bridge key file is empty or invalid.' }
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 10
    $catalog = Invoke-RestMethod -Uri "$baseUrl/models" -Headers @{ Authorization = "Bearer $bridgeKey" } -TimeoutSec 10
} catch {
    $bridgeKey = $null
    throw 'Cannot authenticate to local Qoder Bridge. Check that the Bridge is running and that its port and key directory match.'
}
if ($health.status -ne 'ok' -or $Model -notin @($catalog.data.id)) { throw 'Bridge is not ready or the selected model is unavailable.' }
Write-Host "Bridge ready: $baseUrl | $Model"
if ($CheckOnly) { $bridgeKey = $null; return }

# Same public, non-secret settings file as the editor's API settings dialog.
$configDirectory = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Interval\IntervalComposer'
[IO.Directory]::CreateDirectory($configDirectory) | Out-Null
$configPath = Join-Path $configDirectory 'agent-config.json'
$configJson = @{ base_url=$baseUrl; model=$Model; timeout=120; max_rounds=8; strict=$true; default_key_file=[IO.Path]::GetFullPath($bridgeKeyPath); default_key_endpoint="$baseUrl/chat/completions" } | ConvertTo-Json
$temporaryConfig = Join-Path $configDirectory ('agent-config.' + [guid]::NewGuid().ToString('N') + '.tmp')
[IO.File]::WriteAllText($temporaryConfig, $configJson, (New-Object Text.UTF8Encoding($false)))
Move-Item -LiteralPath $temporaryConfig -Destination $configPath -Force

# Only the new editor process inherits the credential. Never persist or print it.
$previousKey = [Environment]::GetEnvironmentVariable('INTERVAL_AGENT_API_KEY','Process')
try {
    [Environment]::SetEnvironmentVariable('INTERVAL_AGENT_API_KEY',$bridgeKey,'Process')
    # This is the interactive editor the user will operate, not a background helper.
    $editorProcess = Start-Process -FilePath $editorExe -WorkingDirectory $projectDirectory -WindowStyle Normal -PassThru
    Write-Host "Editor started (PID $($editorProcess.Id)). Select Agent and enter your instruction."
} finally {
    [Environment]::SetEnvironmentVariable('INTERVAL_AGENT_API_KEY',$previousKey,'Process')
    $bridgeKey = $null
    $previousKey = $null
}
