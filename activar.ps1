# Activa el entorno del proyecto y manda TODO lo pesado al disco D:
# Uso:  .\activar.ps1
# El disco C: es pequeno (223 GB) y vive lleno; D: y E: tienen cientos de GB libres.

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path

# Caches de herramientas fuera de C:
$env:HF_HOME        = "D:\hf-cache"       # modelos de HuggingFace
$env:TORCH_HOME     = "D:\torch-cache"    # pesos de PyTorch
$env:PIP_CACHE_DIR  = "D:\pip-cache"      # paquetes descargados
$env:TMP            = "D:\tmp"            # temporales (solo en esta sesion)
$env:TEMP           = "D:\tmp"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
$env:PYTHONIOENCODING = "utf-8"           # acentos correctos en consola Windows

foreach ($d in @("D:\hf-cache","D:\torch-cache","D:\pip-cache","D:\tmp","D:\models")) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force $d | Out-Null }
}

Set-Location $raiz
& "$raiz\.venv\Scripts\Activate.ps1"

Write-Host ""
Write-Host "Entorno listo. Caches en D:, temporales en D:\tmp" -ForegroundColor Green
$libreC = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
$libreD = [math]::Round((Get-PSDrive D).Free / 1GB, 2)
Write-Host ("Libre -> C: {0} GB | D: {1} GB" -f $libreC, $libreD) -ForegroundColor DarkGray
if ($libreC -lt 3) {
    Write-Host "AVISO: C: por debajo de 3 GB. Stable Diffusion puede fallar por memoria virtual." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Pipeline completo:  python -m src.runner --no-sync --skip-intelligence --draft" -ForegroundColor DarkGray
