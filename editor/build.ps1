param([string]$DistPath='dist')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot)
$assets=Join-Path (Get-Location) 'app\src\main\assets'
$agentSkills=Join-Path (Get-Location) 'editor\skills'
$agentDefaults=Join-Path (Get-Location) 'editor\agent-defaults.json'
$uiAssets=Join-Path (Get-Location) 'editor\ui_assets'
$editorOutput=Join-Path $DistPath 'IntervalComposer'
$versionFile=Join-Path (Get-Location) 'editor\windows-version.txt'
python -m PyInstaller --noconfirm --windowed --onedir --name IntervalComposer --version-file "$versionFile" --distpath $DistPath --workpath build\composer --specpath build --add-data "$assets;app/src/main/assets" --add-data "$agentSkills;skills" --add-data "$agentDefaults;." --add-data "$uiAssets;ui_assets" --exclude-module tkinter --exclude-module matplotlib editor\launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop editor build failed' }
# Qt 6.11 uses Windows' unversioned ICU API. A different ICU from another
# program on PATH can be picked up by PyInstaller; defer to Windows System32.
if (Test-Path "$env:WINDIR\System32\icuuc.dll") {
    foreach ($name in @('icuuc.dll','icudt78.dll')) {
        $generatedLibrary=Join-Path $editorOutput "_internal\$name"
        if (Test-Path -LiteralPath $generatedLibrary) { Remove-Item -LiteralPath $generatedLibrary }
    }
}
Copy-Item editor\README.md,editor\THIRD_PARTY.md -Destination $editorOutput -Force
Copy-Item editor\skills -Destination $editorOutput -Recurse -Force
Copy-Item editor\AGENT.md -Destination $editorOutput -Force
Copy-Item editor\licenses -Destination $editorOutput -Recurse -Force
# Keep portable documentation links usable after extracting the release archive.
$docsOutput=Join-Path $editorOutput 'docs'
New-Item -ItemType Directory -Force $docsOutput | Out-Null
Copy-Item docs\*.md -Destination $docsOutput -Force
Copy-Item docs\release-0.12.0-tests.json,docs\012-ui-tests.json -Destination $docsOutput -Force
Copy-Item release.json -Destination $editorOutput -Force
$screenOutput=Join-Path $docsOutput 'screenshots'
New-Item -ItemType Directory -Force $screenOutput | Out-Null
Copy-Item docs\screenshots\012 -Destination $screenOutput -Recurse -Force
foreach ($document in @('README.md','AGENT.md')) {
    $documentPath=Join-Path $editorOutput $document
    $content=[IO.File]::ReadAllText($documentPath).Replace('../docs/','docs/')
    [IO.File]::WriteAllText($documentPath,$content,(New-Object Text.UTF8Encoding($false)))
}
Write-Host "Desktop editor: $(Join-Path (Resolve-Path $editorOutput) 'IntervalComposer.exe')"
