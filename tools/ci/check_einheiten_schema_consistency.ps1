$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$candidateVaults = @(
  (Join-Path $repoRoot "..\..\7thVault"),
  (Join-Path $repoRoot "..\7thVault"),
  (Join-Path (Get-Location).Path "7thVault")
) | ForEach-Object {
  try {
    (Resolve-Path $_ -ErrorAction Stop).Path
  } catch {
    $null
  }
} | Where-Object { $_ -and (Test-Path $_) }

$vaultRoot = $candidateVaults | Select-Object -First 1
if (-not $vaultRoot) {
  Write-Output "Schema-Check SKIP: 7thVault nicht vorhanden (CI/isolierte Umgebung)."
  exit 0
}

$root = Get-ChildItem -Path $vaultRoot -Recurse -Directory | Where-Object { $_.Name -eq "10 Unterricht" } | Select-Object -First 1
if ($null -eq $root) {
  Write-Output "Schema-Check SKIP: Ordner '10 Unterricht' nicht gefunden."
  exit 0
}

$allowed = @(
  "Stundentyp",
  "Dauer",
  "Stundenthema",
  "Oberthema",
  "Stundenziel",
  "Teilziele",
  "Kompetenzen",
  "Material",
  "Unterrichtsbesuch",
  "Kompetenzhorizont",
  "Inhaltsübersicht",
  "Vertretungsmaterial",
  "Beobachtungsschwerpunkte",
  "Ressourcen",
  "Baustellen"
)

$required = @("Stundentyp", "Dauer", "Stundenthema")
$validTypes = @("Unterricht", "LZK", "Ausfall", "Hospitation")

$errors = @()
$files = Get-ChildItem -Path $root.FullName -Recurse -File -Filter "*.md" | Where-Object { $_.FullName -match "\\Einheiten\\" }

foreach ($f in $files) {
  $stem = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
  if ($stem -notmatch '^.+ \d{2}-\d{2} .+$') {
    $errors += "Ungueltiger Dateiname: $($f.FullName)"
  }

  $text = Get-Content -Path $f.FullName -Raw -Encoding UTF8
  $m = [regex]::Match($text, '(?s)^---\r?\n(.*?)\r?\n---')
  if (-not $m.Success) {
    $errors += "Fehlendes YAML-Frontmatter: $($f.FullName)"
    continue
  }

  $keys = @()
  $data = @{}
  $currentKey = $null
  foreach ($line in ($m.Groups[1].Value -split "`r?`n")) {
    if ($line -match '^([^:]+):\s*(.*)$') {
      $k = $Matches[1].Trim()
      $v = $Matches[2].Trim().Trim('"')
      $keys += $k
      if ($v -ne "") {
        $data[$k] = $v
        $currentKey = $null
      } else {
        $data[$k] = @()
        $currentKey = $k
      }
      continue
    }
    if ($null -ne $currentKey -and $line -match '^\s*-\s*(.*)$') {
      $item = $Matches[1].Trim().Trim('"')
      if ($item -ne "") {
        $arr = @($data[$currentKey])
        $arr += $item
        $data[$currentKey] = $arr
      }
    }
  }

  foreach ($k in $keys) {
    if ($allowed -notcontains $k) {
      $errors += "Unerlaubtes YAML-Feld '$k' in $($f.FullName)"
    }
  }

  foreach ($k in $required) {
    if (-not $data.ContainsKey($k)) {
      $errors += "Fehlendes Pflichtfeld '$k' in $($f.FullName)"
      continue
    }
    $val = [string]$data[$k]
    if ([string]::IsNullOrWhiteSpace($val)) {
      $errors += "Leeres Pflichtfeld '$k' in $($f.FullName)"
    }
  }

  if ($data.ContainsKey("Stundentyp")) {
    if ($validTypes -notcontains ([string]$data["Stundentyp"])) {
      $errors += "Ungueltiger Stundentyp '$($data["Stundentyp"])' in $($f.FullName)"
    }
  }
}

if ($errors.Count -gt 0) {
  Write-Output "Schema-Check FEHLGESCHLAGEN:"
  $errors | ForEach-Object { Write-Output "- $_" }
  exit 1
}

Write-Output "Schema-Check OK: $($files.Count) Einheitendateien geprueft."
exit 0
