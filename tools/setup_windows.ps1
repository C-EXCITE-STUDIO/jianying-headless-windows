param(
    [Parameter(Mandatory = $true)][string]$Target,
    [string]$PythonExecutable = 'python',
    [string]$DependencyRepository = 'https://github.com/aoguai/pyJianYingDraft.git',
    [switch]$SkipPythonInstall
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TargetPath = [IO.Path]::GetFullPath($Target)
$DependencyPath = Join-Path $TargetPath 'pyJianYingDraft'
$BaseCommit = '2b6ed48b0f096e5a76a5b8a68a6d7d233defb463'
$ExpectedFiles = @{
    'pyJianYingDraft/local_materials.py' = 'b00f71b75996ec9fd8ae03e89e6e6109ae1fda198e07c9a006aab3b7b3ba9476'
    'pyJianYingDraft/text_segment.py' = '4d54e4e1162cb75c2e3089f224b67c4aa4b024117dbe76fe5d45afff02e42579'
    'pyJianYingDraft/draft_file_paths.py' = '71d298645e72c09b11dceb2fd0f387000275de70e3ff5e694a8c0c18155736d8'
    'pyJianYingDraft/draft_codec.py' = 'd2fdeb8ffab4fb198c0cc4019f4df61cdffe1463f29db2e7baee5d3841156a3e'
}

if (Test-Path -LiteralPath $TargetPath) {
    throw "目標已存在，不覆寫：$TargetPath"
}
New-Item -ItemType Directory -Path $TargetPath | Out-Null
$TemporaryPath = Join-Path $TargetPath 'temp'
New-Item -ItemType Directory -Path $TemporaryPath | Out-Null
$env:TEMP = $TemporaryPath
$env:TMP = $TemporaryPath
$env:PIP_CACHE_DIR = Join-Path $TargetPath 'pip-cache'

if (Test-Path -LiteralPath $DependencyRepository -PathType Container) {
    # A local shallow checkout can be used to rehearse setup without network.
    New-Item -ItemType Directory -Path $DependencyPath | Out-Null
    $ArchivePath = Join-Path $TargetPath 'pyJianYingDraft-base.tar'
    & git -C $DependencyRepository archive --format=tar --output $ArchivePath $BaseCommit
    if ($LASTEXITCODE -ne 0) { throw "本機來源找不到固定基線 $BaseCommit" }
    & tar -xf $ArchivePath -C $DependencyPath
    if ($LASTEXITCODE -ne 0) { throw '無法展開本機 pyJianYingDraft 基線' }
    Remove-Item -LiteralPath $ArchivePath
} else {
    & git clone --no-checkout $DependencyRepository $DependencyPath
    if ($LASTEXITCODE -ne 0) { throw '無法取得 pyJianYingDraft 原始碼' }
    & git -C $DependencyPath checkout --detach $BaseCommit
    if ($LASTEXITCODE -ne 0) { throw "找不到固定基線 $BaseCommit" }
}

$PatchRoot = Join-Path $ProjectRoot 'third_party/pyJianYingDraft/patches'
$Patches = @(Get-ChildItem -LiteralPath $PatchRoot -Filter '*.patch' -File | Sort-Object Name)
if ($Patches.Count -ne 2) { throw 'pyJianYingDraft 修補檔數量不符' }
foreach ($Patch in $Patches) {
    & git -C $DependencyPath apply --check $Patch.FullName
    if ($LASTEXITCODE -ne 0) { throw "無法套用修補：$($Patch.Name)" }
    & git -C $DependencyPath apply $Patch.FullName
    if ($LASTEXITCODE -ne 0) { throw "套用修補失敗：$($Patch.Name)" }
}
foreach ($Entry in $ExpectedFiles.GetEnumerator()) {
    $FilePath = Join-Path $DependencyPath $Entry.Key
    $Actual = (Get-FileHash -LiteralPath $FilePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $Entry.Value) { throw "依賴原始碼雜湊不符：$($Entry.Key)" }
}

if (-not $SkipPythonInstall) {
    $VenvPath = Join-Path $TargetPath '.venv'
    & $PythonExecutable -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) { throw '無法建立 Python 虛擬環境' }
    $VenvPython = Join-Path $VenvPath 'Scripts/python.exe'
    & $VenvPython -m pip install --requirement (Join-Path $ProjectRoot 'requirements-windows.txt')
    if ($LASTEXITCODE -ne 0) { throw '無法安裝固定版本的 Python 依賴' }
    & $VenvPython -m pip install --no-deps --editable $DependencyPath
    if ($LASTEXITCODE -ne 0) { throw '無法安裝 pyJianYingDraft 本機修補版' }
    & $VenvPython -c 'import pyJianYingDraft, pymediainfo, imageio, uiautomation; print("Windows Python 依賴就緒")'
    if ($LASTEXITCODE -ne 0) { throw '依賴匯入檢查失敗' }
}
Write-Output "依賴已固定於：$TargetPath"
