function Get-Sha256Hex([string]$Path) {
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-ImageScrollDescriptor([string]$RepositoryRoot) {
  $path = Join-Path $RepositoryRoot 'datasets/image-scroll/v1/dataset.json'
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Dataset descriptor is missing: $path" }
  return (Get-Content -LiteralPath $path -Raw | ConvertFrom-Json)
}

function Assert-SafeDatasetPath([string]$RelativePath) {
  if ([string]::IsNullOrWhiteSpace($RelativePath)) { throw 'Image-scroll manifest contains an empty path' }
  $invalid = [string]::IsNullOrWhiteSpace($RelativePath) -or $RelativePath.Contains('\') -or
      $RelativePath.StartsWith('/') -or $RelativePath -match '^[A-Za-z]:'
  foreach ($segment in $RelativePath.Split('/')) {
    if ($segment -eq '' -or $segment -eq '.' -or $segment -eq '..') { $invalid = $true }
  }
  if ($invalid) {
    throw "Unsafe path in image-scroll manifest: $RelativePath"
  }
}

function Test-ImageScrollPayload($Descriptor, $Manifest, [string]$FilesRoot) {
  $files = @($Manifest.files)
  if ($files.Count -ne [int]$Descriptor.expectedFileCount -or
      [int]$Manifest.fileCount -ne [int]$Descriptor.expectedFileCount) {
    throw "Dataset manifest count mismatch: actual=$($files.Count), expected=$($Descriptor.expectedFileCount)"
  }
  $root = [IO.Path]::GetFullPath($FilesRoot).TrimEnd('\') + '\'
  $seen = @{}
  $formats = @{ jpeg = 0; png = 0; other = 0 }
  foreach ($entry in $files) {
    Assert-SafeDatasetPath ([string]$entry.path)
    $relative = ([string]$entry.path).Replace('/', [IO.Path]::DirectorySeparatorChar)
    $path = [IO.Path]::GetFullPath((Join-Path $FilesRoot $relative))
    if (-not $path.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { throw "Manifest path escapes dataset: $($entry.path)" }
    if ($seen.ContainsKey($relative)) { throw "Duplicate path in image-scroll manifest: $($entry.path)" }
    $seen[$relative] = $true
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Dataset file is missing: $($entry.path)" }
    $item = Get-Item -LiteralPath $path
    if ($item.Length -ne [long]$entry.bytes -or (Get-Sha256Hex $path) -ne ([string]$entry.sha256).ToLowerInvariant()) {
      throw "Dataset size or SHA-256 mismatch: $($entry.path)"
    }
    $stream = [IO.File]::OpenRead($path)
    try {
      $header = New-Object byte[] 8
      $read = $stream.Read($header, 0, $header.Length)
    } finally { $stream.Dispose() }
    if ($read -ge 3 -and $header[0] -eq 255 -and $header[1] -eq 216 -and $header[2] -eq 255) { $formats.jpeg++ }
    elseif ($read -ge 8 -and $header[0] -eq 137 -and $header[1] -eq 80 -and $header[2] -eq 78 -and
        $header[3] -eq 71 -and $header[4] -eq 13 -and $header[5] -eq 10 -and $header[6] -eq 26 -and $header[7] -eq 10) { $formats.png++ }
    else { $formats.other++ }
  }
  $actual = @{}
  foreach ($file in Get-ChildItem -LiteralPath $FilesRoot -File -Recurse) {
    $relative = $file.FullName.Substring($root.Length).Replace('\', '/')
    $actual[$relative] = $true
  }
  if ($actual.Count -ne $seen.Count) { throw "Dataset extraction has extra or missing files: actual=$($actual.Count), manifest=$($seen.Count)" }
  foreach ($key in $actual.Keys) { if (-not $seen.ContainsKey($key.Replace('/', [IO.Path]::DirectorySeparatorChar))) { throw "Unlisted dataset file: $key" } }
  foreach ($format in $Descriptor.historicalFormatCounts.PSObject.Properties) {
    if ($formats[$format.Name] -ne [int]$format.Value) {
      throw "Dataset format count mismatch for $($format.Name): actual=$($formats[$format.Name]), expected=$($format.Value)"
    }
  }
  if ($formats.other -ne 0) { throw "Dataset contains $($formats.other) unsupported image files" }
  return $formats
}

function Get-Sha256Sums([string]$Path) {
  $values = @{}
  foreach ($line in Get-Content -LiteralPath $Path) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    if ($line -notmatch '^([0-9a-fA-F]{64})\s+\*?([^\s]+)$') { throw 'Malformed SHA256SUMS entry' }
    $name = [IO.Path]::GetFileName($Matches[2])
    if ($values.ContainsKey($name)) { throw "Duplicate SHA256SUMS object: $name" }
    $values[$name] = $Matches[1].ToLowerInvariant()
  }
  return $values
}

function Test-ImageScrollCache([string]$RepositoryRoot, [string]$CachePath) {
  $descriptor = Get-ImageScrollDescriptor $RepositoryRoot
  $objects = Join-Path $CachePath 'objects'
  $files = Join-Path $CachePath 'files'
  foreach ($name in @('SHA256SUMS', 'manifest.json', 'totalcross-image-scroll-v1.zip')) {
    $path = Join-Path $objects $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Dataset object is missing: $path" }
  }
  $sums = Get-Sha256Sums (Join-Path $objects 'SHA256SUMS')
  if ($sums['manifest.json'] -ne $descriptor.integrity.manifestSha256 -or
      $sums['totalcross-image-scroll-v1.zip'] -ne $descriptor.integrity.archiveSha256) {
    throw 'SHA256SUMS does not match the pinned dataset descriptor'
  }
  if ((Get-Sha256Hex (Join-Path $objects 'manifest.json')) -ne $descriptor.integrity.manifestSha256 -or
      (Get-Sha256Hex (Join-Path $objects 'totalcross-image-scroll-v1.zip')) -ne $descriptor.integrity.archiveSha256) {
    throw 'Downloaded dataset object hash does not match the pinned descriptor'
  }
  $manifest = Get-Content -LiteralPath (Join-Path $objects 'manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.version -and $manifest.version -ne $descriptor.version) { throw 'Dataset manifest version mismatch' }
  if ($manifest.dataset -and $manifest.dataset -ne $descriptor.id) { throw 'Dataset manifest id mismatch' }
  $formats = Test-ImageScrollPayload $descriptor $manifest $files
  return [pscustomobject]@{
    id = $descriptor.id
    version = $descriptor.version
    manifestSha256 = $descriptor.integrity.manifestSha256
    fileCount = [int]$manifest.fileCount
    formatCounts = $formats
  }
}

function Receive-ImageScrollDataset([string]$RepositoryRoot, [string]$CachePath) {
  if (Test-Path -LiteralPath $CachePath) {
    return Test-ImageScrollCache $RepositoryRoot $CachePath
  }
  $descriptor = Get-ImageScrollDescriptor $RepositoryRoot
  $parent = Split-Path -Parent ([IO.Path]::GetFullPath($CachePath))
  [IO.Directory]::CreateDirectory($parent) | Out-Null
  $temporary = Join-Path $parent ('.image-scroll-fetch-' + [guid]::NewGuid().ToString('N'))
  $objects = Join-Path $temporary 'objects'
  $files = Join-Path $temporary 'files'
  [IO.Directory]::CreateDirectory($objects) | Out-Null
  $installedCache = $false
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $urls = @{
      'SHA256SUMS' = [string]$descriptor.artifacts.sha256sums
      'manifest.json' = [string]$descriptor.artifacts.manifest
      'totalcross-image-scroll-v1.zip' = [string]$descriptor.artifacts.archive
    }
    foreach ($name in $urls.Keys) {
      Invoke-WebRequest -Uri $urls[$name] -OutFile (Join-Path $objects $name) -UseBasicParsing -TimeoutSec 120
    }
    $sums = Get-Sha256Sums (Join-Path $objects 'SHA256SUMS')
    if ($sums['manifest.json'] -ne $descriptor.integrity.manifestSha256 -or
        $sums['totalcross-image-scroll-v1.zip'] -ne $descriptor.integrity.archiveSha256 -or
        (Get-Sha256Hex (Join-Path $objects 'manifest.json')) -ne $descriptor.integrity.manifestSha256 -or
        (Get-Sha256Hex (Join-Path $objects 'totalcross-image-scroll-v1.zip')) -ne $descriptor.integrity.archiveSha256) {
      throw 'Downloaded image-scroll objects do not match pinned SHA-256 values'
    }
    $manifest = Get-Content -LiteralPath (Join-Path $objects 'manifest.json') -Raw | ConvertFrom-Json
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Directory]::CreateDirectory($files) | Out-Null
    $archive = [IO.Compression.ZipFile]::OpenRead((Join-Path $objects 'totalcross-image-scroll-v1.zip'))
    try {
      $archiveNames = @{}
      foreach ($entry in $archive.Entries) {
        $name = $entry.FullName
        $isDirectory = $name.EndsWith('/')
        if ($isDirectory) { $name = $name.TrimEnd('/') }
        Assert-SafeDatasetPath $name
        if ($archiveNames.ContainsKey($name)) { throw "Duplicate path in image-scroll ZIP: $name" }
        $archiveNames[$name] = $true
        if ($isDirectory) { continue }
        $relative = $name.Replace('/', [IO.Path]::DirectorySeparatorChar)
        $destination = [IO.Path]::GetFullPath((Join-Path $files $relative))
        $root = [IO.Path]::GetFullPath($files).TrimEnd('\') + '\'
        if (-not $destination.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { throw "ZIP path escapes dataset: $name" }
        [IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) | Out-Null
        $input = $entry.Open()
        $output = [IO.File]::Create($destination)
        try { $input.CopyTo($output) } finally { $output.Dispose(); $input.Dispose() }
      }
    } finally { $archive.Dispose() }
    $null = Test-ImageScrollPayload $descriptor $manifest $files
    [IO.Directory]::CreateDirectory($CachePath) | Out-Null
    $installedCache = $true
    Move-Item -LiteralPath $objects -Destination (Join-Path $CachePath 'objects')
    Move-Item -LiteralPath $files -Destination (Join-Path $CachePath 'files')
    return Test-ImageScrollCache $RepositoryRoot $CachePath
  } catch {
    if ($installedCache -and (Test-Path -LiteralPath $CachePath)) {
      Remove-Item -LiteralPath $CachePath -Recurse -Force
    }
    throw
  } finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
  }
}
