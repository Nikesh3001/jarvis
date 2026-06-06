param(
  [string]$Destination = "$env:USERPROFILE\Desktop\jarvis-ubuntu.zip"
)

$src = "$PSScriptRoot\.."
$exclude = @(
  '__pycache__', 'venv', '.venv', '.git', 'conversations', 'plans',
  'memory_store', '*.zip', '*.log'
)

Write-Host "[*] Packaging FRIDAY for transfer to Ubuntu..."
Write-Host "[*] Source: $src"
Write-Host "[*] Destination: $Destination"

$compressParams = @{
  Path             = $src
  DestinationPath  = $Destination
  CompressionLevel = "Optimal"
}

try {
  Compress-Archive @compressParams
  Write-Host "[OK] Created: $Destination"
  Write-Host "[*] Size: $((Get-Item $Destination).Length / 1MB -as [int]) MB"
  Write-Host "[*] Transfer this .zip to Ubuntu via USB, SCP, or cloud."
} catch {
  Write-Warn "Compress-Archive failed, trying with 7z..."
  if (Get-Command 7z -ErrorAction SilentlyContinue) {
    7z a -tzip "$Destination" "$src\*" -xr!__pycache__ -xr!venv -xr!.venv -xr!.git -xr!conversations -xr!plans -xr!memory_store
    Write-Host "[OK] Created with 7z: $Destination"
  } else {
    Write-Error "Failed to create zip. Copy the jarvis folder manually."
  }
}

Write-Host ""
Write-Host "Quick copy via SCP (both on same LAN):"
Write-Host "  scp -r $src user@`$(ubuntu-ip):~/jarvis"
