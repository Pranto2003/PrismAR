$ErrorActionPreference = "Stop"

$AppName = "PrismAR"
$Version = "v1.0"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AssetsDir = Join-Path $ProjectRoot "assets"
$ModelPath = Join-Path $AssetsDir "hand_landmarker.task"
$ModelUrl = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
$DistExe = Join-Path $ProjectRoot "dist\$AppName.exe"
$ReleaseRoot = Join-Path $ProjectRoot "release"
$ReleaseDir = Join-Path $ReleaseRoot "$AppName-$Version"
$ZipPath = Join-Path $ReleaseRoot "$AppName-$Version.zip"

Write-Host ""
Write-Host "=== $AppName Windows Build ==="
Write-Host "Project: $ProjectRoot"
Write-Host ""

Set-Location $ProjectRoot

if (-not (Test-Path $AssetsDir)) {
    New-Item -ItemType Directory -Path $AssetsDir | Out-Null
}

if (-not (Test-Path $ModelPath)) {
    Write-Host "MediaPipe hand model not found. Downloading..."
    Invoke-WebRequest -Uri $ModelUrl -OutFile $ModelPath
}

Write-Host "Building one-file windowed EXE..."
python -m PyInstaller --noconfirm --clean PrismAR.spec

if (-not (Test-Path $DistExe)) {
    throw "Build failed: $DistExe was not created."
}

Write-Host "Preparing release folder..."
if (Test-Path $ReleaseDir) {
    Remove-Item -Recurse -Force $ReleaseDir
}
if (-not (Test-Path $ReleaseRoot)) {
    New-Item -ItemType Directory -Path $ReleaseRoot | Out-Null
}
New-Item -ItemType Directory -Path $ReleaseDir | Out-Null

Copy-Item $DistExe (Join-Path $ReleaseDir "$AppName.exe") -Force
Copy-Item (Join-Path $ProjectRoot "README.md") (Join-Path $ReleaseDir "README.md") -Force

$LicensePath = Join-Path $ProjectRoot "LICENSE"
if (Test-Path $LicensePath) {
    Copy-Item $LicensePath (Join-Path $ReleaseDir "LICENSE") -Force
}

# The EXE already contains bundled assets. The external assets folder is also
# included in the release ZIP as a transparent backup/manual fallback.
$ReleaseAssetsDir = Join-Path $ReleaseDir "assets"
New-Item -ItemType Directory -Path $ReleaseAssetsDir | Out-Null
Copy-Item $ModelPath (Join-Path $ReleaseAssetsDir "hand_landmarker.task") -Force
if (Test-Path (Join-Path $AssetsDir "README.md")) {
    Copy-Item (Join-Path $AssetsDir "README.md") (Join-Path $ReleaseAssetsDir "README.md") -Force
}

if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}

Write-Host "Creating ZIP release..."
Compress-Archive -Path (Join-Path $ReleaseDir "*") -DestinationPath $ZipPath -Force

Write-Host ""
Write-Host "Build complete."
Write-Host "EXE: $DistExe"
Write-Host "Release folder: $ReleaseDir"
Write-Host "ZIP: $ZipPath"
Write-Host ""
