[CmdletBinding()]
param(
  [ValidateSet('decode', 'scroll', 'preparation', 'pacing')]
  [string]$Family = 'scroll',
  [string[]]$Profile,
  [string[]]$Source,
  [string[]]$Scale,
  [string[]]$Order,
  [string[]]$Workload,
  [int]$Rounds = 3,
  [int]$Warmups = 1,
  [int]$TimeoutSeconds = 300,
  [int]$Width = 540,
  [int]$Height = 960,
  [switch]$Diagnostics,
  [switch]$FailFast,
  [switch]$SigbusStress,
  [switch]$FetchDataset,
  [switch]$VerifyDataset,
  [string]$RuntimeSource = $env:TOTALCROSS_SOURCE,
  [string]$DatasetCache,
  [string]$PackageManifest,
  [string]$ResultsDirectory
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot 'dataset.ps1')

function Get-GitValue([string]$Directory, [string[]]$Arguments) {
  $value = & git -C $Directory @Arguments 2>$null
  if ($LASTEXITCODE -ne 0) { throw "Cannot read Git identity from $Directory" }
  return ($value -join "`n").Trim()
}

function Get-Hash([string]$Path) {
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-RequiredFields($Value, $SchemaPath, [string]$Description) {
  $schema = Get-Content -LiteralPath $SchemaPath -Raw | ConvertFrom-Json
  foreach ($field in $schema.required) {
    if ($null -eq $Value.PSObject.Properties[[string]$field]) { throw "$Description is missing required field $field" }
  }
  return $schema
}

function Assert-RunRecord($Run, [string]$Phase, [int]$RoundNumber, $EnvironmentSchema) {
  $schemaPath = Join-Path $repoRoot 'schemas/benchmark-run-v1.schema.json'
  $schema = Assert-RequiredFields $Run $schemaPath 'run record'
  if ($Run.schemaVersion -ne 1 -or $Run.recordType -ne 'run' -or $Run.family -ne $script:activeFamily -or
      $Run.phase -ne $Phase -or [int]$Run.round -ne $RoundNumber) { throw 'Run record identity or version is invalid' }
  if (($Run.round -isnot [int] -and $Run.round -isnot [long]) -or $Run.round -lt 0) { throw 'Run round must be a non-negative integer' }
  if ($Run.family -notin @('decode', 'scroll', 'preparation', 'pacing') -or
      $Run.phase -notin @('warmup', 'measured', 'diagnostic')) { throw 'Run record has an unsupported family or phase' }
  foreach ($field in @('workload', 'profile', 'runtimeSourceCommit', 'runtimeIdentity', 'renderer', 'runtimeConfigurationReport')) {
    if ($Run.PSObject.Properties[$field].Value -isnot [string]) { throw "Run field $field must be a string" }
  }
  if ($Run.runtimeSourceCommit -ne $script:runtimeCommit -or $Run.benchmarkSourceCommit -ne $script:benchmarkCommit) {
    throw 'Run record source commits do not match the selected checkouts'
  }
  if ($Run.diagnosticsSupported -isnot [bool] -or $Run.diagnosticsEnabled -isnot [bool]) {
    throw 'Run record diagnostic flags must be booleans'
  }
  if ($Run.environment -isnot [System.Management.Automation.PSCustomObject]) { throw 'Run environment must be an object' }
  foreach ($field in $EnvironmentSchema.required) {
    if ($null -eq $Run.environment.PSObject.Properties[[string]$field]) { throw "Run environment is missing $field" }
  }
  if ($Run.environment.benchmarkWorkingTreeDirty -isnot [bool]) { throw 'Environment dirty flag must be boolean' }
  if ($Run.durationsNs -isnot [System.Management.Automation.PSCustomObject]) { throw 'durationsNs must be an object' }
  if ($Run.measurements -isnot [System.Management.Automation.PSCustomObject]) { throw 'measurements must be an object' }
  foreach ($duration in $Run.durationsNs.PSObject.Properties) {
    if (($duration.Value -isnot [int] -and $duration.Value -isnot [long]) -or [long]$duration.Value -lt 0) {
      throw "Invalid duration value: $($duration.Name)"
    }
  }
}

function Assert-SummaryRecord($Summary, $Run, $EnvironmentSchema) {
  $schemaPath = Join-Path $repoRoot 'schemas/benchmark-summary-v1.schema.json'
  $null = Assert-RequiredFields $Summary $schemaPath 'summary record'
  if ($Summary.schemaVersion -ne 1 -or $Summary.recordType -ne 'summary' -or
      $Summary.family -ne $Run.family -or $Summary.workload -ne $Run.workload -or $Summary.profile -ne $Run.profile) {
    throw 'Final summary identity is invalid'
  }
  if (($Summary.failures -isnot [int] -and $Summary.failures -isnot [long]) -or $Summary.failures -lt 0) {
    throw 'Summary failures must be a non-negative integer'
  }
  if (@($Summary.rounds).Count -ne 1 -or
      (ConvertTo-Json -InputObject $Summary.rounds[0] -Depth 100 -Compress) -ne
      (ConvertTo-Json -InputObject $Run -Depth 100 -Compress)) { throw 'Summary must contain exactly the emitted run record' }
  if ($Summary.environment -isnot [System.Management.Automation.PSCustomObject]) { throw 'Summary environment must be an object' }
  foreach ($field in $EnvironmentSchema.required) {
    if ($null -eq $Summary.environment.PSObject.Properties[[string]$field]) { throw "Summary environment is missing $field" }
  }
}

function Assert-PackageManifest([string]$ManifestPath, [string]$RuntimeCommit, [string]$BenchmarkCommit) {
  $schemaPath = Join-Path $repoRoot 'schemas/benchmark-package-v1.schema.json'
  $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
  $null = Assert-RequiredFields $manifest $schemaPath 'package manifest'
  if ($manifest.schemaVersion -ne 1 -or $manifest.packageType -ne 'image-rendering-windows' -or $manifest.platform -ne 'windows') {
    throw 'Package manifest type, platform, or version is unsupported'
  }
  if ($manifest.totalcrossSourceCommit -ne $RuntimeCommit -or $manifest.runtimeArtifactSourceCommit -ne $RuntimeCommit) {
    throw 'Package and Windows runtime source commits do not match the selected TotalCross checkout'
  }
  if ($manifest.benchmarkSourceCommit -ne $BenchmarkCommit -or $manifest.benchmarkWorkingTreeDirty) {
    throw 'Package was built from a different or dirty benchmark source'
  }
  $allProfiles = @('default', 'target-color', 'physical-variant', 'raster-variants', 'compact',
    'scroll-reuse', 'prepared-legacy', 'prepared-semaphore', 'combined-standard', 'combined-compact')
  $manifestProfileNames = (@($manifest.profiles.PSObject.Properties.Name | Sort-Object) -join ',')
  $expectedProfileNames = (@($allProfiles | Sort-Object) -join ',')
  if (($manifest.profileInventory -join ',') -ne ($allProfiles -join ',') -or
      $manifestProfileNames -ne $expectedProfileNames) {
    throw 'Package does not contain the complete named profile inventory'
  }
  $packageRoot = Split-Path -Parent $ManifestPath
  foreach ($profileName in $allProfiles) {
    $profile = $manifest.profiles.$profileName
    foreach ($item in @($profile.runtimeFiles) + @([pscustomobject]@{ path = $profile.executable; sha256 = $null })) {
      $relative = [string]$item.path
      if ([string]::IsNullOrWhiteSpace($relative) -or [IO.Path]::IsPathRooted($relative) -or $relative.Contains('..')) {
        throw "Unsafe package path for profile $profileName"
      }
      $path = [IO.Path]::GetFullPath((Join-Path $packageRoot $relative))
      if (-not $path.StartsWith(([IO.Path]::GetFullPath($packageRoot).TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase) -or
          -not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Package file is missing or escapes package: $relative" }
      if ($item.sha256 -and (Get-Hash $path) -ne $item.sha256) { throw "Package file hash mismatch: $relative" }
    }
    $exe = Join-Path $packageRoot $profile.executable
    if ((Get-Hash $exe) -notin @($manifest.runtimeBinaries | Where-Object { $_.path -eq $profile.executable } | ForEach-Object { $_.sha256 })) {
      throw "Profile executable hash is missing from runtimeBinaries: $profileName"
    }
  }
  $descriptor = Get-ImageScrollDescriptor $repoRoot
  if ($manifest.dataset.id -ne $descriptor.id -or $manifest.dataset.version -ne $descriptor.version -or
      $manifest.dataset.manifestSha256 -ne $descriptor.integrity.manifestSha256) { throw 'Package dataset identity differs from the pinned descriptor' }
  return $manifest
}

function Invoke-BenchmarkChild($ProfilePackage, $Config, [string]$WorkingDirectory, [string]$ProcessDirectory,
    [string]$Phase, [int]$RoundNumber, [int]$Timeout) {
  [IO.Directory]::CreateDirectory($ProcessDirectory) | Out-Null
  $json = ConvertTo-Json -InputObject $Config -Depth 100
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  [IO.File]::WriteAllText((Join-Path $ProcessDirectory 'tcbench-run.json'), $json, $utf8)
  [IO.File]::WriteAllText((Join-Path $WorkingDirectory 'tcbench-run.json'), $json, $utf8)
  $debugConsole = Join-Path $WorkingDirectory 'DebugConsole.txt'
  if (Test-Path -LiteralPath $debugConsole) { Remove-Item -LiteralPath $debugConsole -Force }
  $stdoutPath = Join-Path $ProcessDirectory 'stdout.log'
  $stderrPath = Join-Path $ProcessDirectory 'stderr.log'
  $processInfo = New-Object Diagnostics.ProcessStartInfo
  $processInfo.FileName = Join-Path (Split-Path -Parent $PackageManifest) $ProfilePackage.executable
  $processInfo.WorkingDirectory = $WorkingDirectory
  $processInfo.UseShellExecute = $false
  $processInfo.RedirectStandardOutput = $true
  $processInfo.RedirectStandardError = $true
  $process = New-Object Diagnostics.Process
  $process.StartInfo = $processInfo
  $timer = [Diagnostics.Stopwatch]::StartNew()
  if (-not $process.Start()) { throw 'Could not start the packaged TotalCross process' }
  $stdoutTask = $process.StandardOutput.ReadToEndAsync()
  $stderrTask = $process.StandardError.ReadToEndAsync()
  if (-not $process.WaitForExit($Timeout * 1000)) {
    $process.Kill()
    $process.WaitForExit()
    $timer.Stop()
    [IO.File]::WriteAllText($stdoutPath, $stdoutTask.Result, $utf8)
    [IO.File]::WriteAllText($stderrPath, $stderrTask.Result, $utf8)
    if (Test-Path -LiteralPath $debugConsole) { Copy-Item -LiteralPath $debugConsole -Destination (Join-Path $ProcessDirectory 'DebugConsole.txt') }
    throw "Child process timed out after $Timeout seconds"
  }
  $process.WaitForExit()
  $timer.Stop()
  $stdout = $stdoutTask.Result
  $stderr = $stderrTask.Result
  [IO.File]::WriteAllText($stdoutPath, $stdout, $utf8)
  [IO.File]::WriteAllText($stderrPath, $stderr, $utf8)
  if (Test-Path -LiteralPath $debugConsole) { Copy-Item -LiteralPath $debugConsole -Destination (Join-Path $ProcessDirectory 'DebugConsole.txt') }
  if ($process.ExitCode -ne 0) { throw "Child exited with status $($process.ExitCode)" }
  if ($Phase -eq 'preflight') {
    return [pscustomobject]@{
      exitCode = $process.ExitCode
      runnerWallTimeNs = [long]([double]$timer.ElapsedTicks * 1000000000.0 / [double][Diagnostics.Stopwatch]::Frequency)
    }
  }
  $protocolOutput = $stdout
  if (-not $protocolOutput.Contains('TCBENCH_JSON ') -and (Test-Path -LiteralPath $debugConsole)) {
    $protocolOutput = Get-Content -LiteralPath $debugConsole -Raw
  }
  $records = @()
  foreach ($line in ($protocolOutput -split "`r?`n")) {
    if (-not $line.StartsWith('TCBENCH_JSON ')) { continue }
    try { $records += ,($line.Substring(13) | ConvertFrom-Json) } catch { throw 'Malformed TCBENCH_JSON output' }
  }
  if ($records.Count -ne 2 -or $records[0].recordType -ne 'run' -or $records[1].recordType -ne 'summary') {
    throw 'Child output must contain exactly one run and one final summary'
  }
  $runRecord = $records[0]
  $summary = $records[1]
  $environmentSchema = Get-Content -LiteralPath (Join-Path $repoRoot 'schemas/environment-v1.schema.json') -Raw | ConvertFrom-Json
  Assert-RunRecord $runRecord $Phase $RoundNumber $environmentSchema
  Assert-SummaryRecord $summary $runRecord $environmentSchema
  if ($summary.rounds[0].round -ne $runRecord.round -or $summary.rounds[0].phase -ne $runRecord.phase) {
    throw 'Final summary does not contain the requested run record'
  }
  return [pscustomobject]@{
    run = $runRecord
    summary = $summary
    runnerWallTimeNs = [long]([double]$timer.ElapsedTicks * 1000000000.0 / [double][Diagnostics.Stopwatch]::Frequency)
  }
}

function Get-Percentile([double[]]$Values, [double]$Fraction) {
  $sorted = @($Values | Sort-Object)
  $position = ($sorted.Count - 1) * $Fraction
  $low = [int][Math]::Floor($position)
  $high = [int][Math]::Ceiling($position)
  return [double]$sorted[$low] + (([double]$sorted[$high] - [double]$sorted[$low]) * ($position - $low))
}

function New-BenchmarkConfig($Cell, [int]$RoundNumber, [string]$Phase, [bool]$Preflight,
    $PackageProfile, $RuntimeFiles, [string]$RuntimeIdentity, $Environment, $DatasetInfo) {
  $datasetRoot = if ($DatasetInfo) { Join-Path $DatasetCache 'files' } else { $null }
  $manifestPath = if ($DatasetInfo) { Join-Path $DatasetCache 'objects/manifest.json' } else { $null }
  $tczPrefix = if ($DatasetInfo) { 'image-scroll/' } else { $null }
  $dimensions = if ($Family -in @('scroll', 'preparation')) { [pscustomobject]@{ width = $Width; height = $Height } } else { $null }
  $axes = [ordered]@{}
  foreach ($key in @('source', 'scale', 'order')) { if ($Cell.ContainsKey($key)) { $axes[$key] = $Cell[$key] } }
  return [pscustomobject]@{
    schemaVersion = 1; family = $Family; profile = $Cell.profile; workload = $Cell.workload
    source = $Cell.source; scale = $Cell.scale; order = $Cell.order
    round = $RoundNumber; phase = $Phase; preflight = $Preflight
    dataset = $DatasetInfo; datasetRoot = $datasetRoot; datasetManifestPath = $manifestPath; datasetTczPrefix = $tczPrefix
    runtimeSourceCommit = $script:runtimeCommit; benchmarkSourceCommit = $script:benchmarkCommit
    runtimeIdentity = $RuntimeIdentity; runtimeFiles = $RuntimeFiles; environment = $Environment
    logicalDimensions = $dimensions; drawableDimensions = $null; diagnosticsEnabled = [bool]$Diagnostics
    datasetAxes = $axes; seed = $(if ($Cell.order -eq 'seeded-random') { 12012026 } else { $null })
    pacingWorkload = $(if ($Family -eq 'pacing') { $Cell.workload } else { $null })
    cacheDirectory = $DatasetCache; resultProtocolPrefix = 'TCBENCH_JSON '; appPackage = $PackageProfile
  }
}

function Get-CellList {
  $profiles = if ($Profile) { @($Profile) } else {
    switch ($Family) {
      'decode' { @('default', 'compact') }
      'scroll' { @('default', 'target-color', 'physical-variant', 'raster-variants', 'scroll-reuse', 'combined-standard', 'combined-compact') }
      'preparation' { @('default', 'prepared-legacy', 'prepared-semaphore', 'combined-standard', 'combined-compact') }
      'pacing' { @('default') }
    }
  }
  $allowedProfiles = @('default', 'target-color', 'physical-variant', 'raster-variants', 'compact', 'scroll-reuse',
    'prepared-legacy', 'prepared-semaphore', 'combined-standard', 'combined-compact')
  foreach ($value in $profiles) { if ($value -notin $allowedProfiles) { throw "Unsupported profile: $value" } }
  $cells = New-Object 'System.Collections.Generic.List[object]'
  if ($Family -eq 'decode') {
    $sources = if ($Source) { @($Source) } else { @('filesystem', 'tcz') }
    $scales = if ($Scale) { @($Scale) } else { @('full', 'half') }
    $orders = if ($Order) { @($Order) } else { @('sequential', 'seeded-random') }
    foreach ($s in $sources) { if ($s -notin @('filesystem', 'tcz')) { throw "Unsupported source: $s" } }
    foreach ($s in $scales) { if ($s -notin @('full', 'half')) { throw "Unsupported scale: $s" } }
    foreach ($s in $orders) { if ($s -notin @('sequential', 'seeded-random')) { throw "Unsupported order: $s" } }
    foreach ($profileName in $profiles) { foreach ($s in $sources) { foreach ($scaleName in $scales) { foreach ($orderName in $orders) {
      $cells.Add(@{ profile = $profileName; workload = 'decode'; source = $s; scale = $scaleName; order = $orderName })
    } } } }
  } elseif ($Family -eq 'pacing') {
    $workloads = if ($Workload) { @($Workload) } else { @('flick-40', 'flick-60', 'synthetic-16ms', 'synthetic-16.667ms') }
    foreach ($value in $workloads) { if ($value -notin @('flick-40', 'flick-60', 'synthetic-16ms', 'synthetic-16.667ms')) { throw "Unsupported pacing workload: $value" } }
    foreach ($profileName in $profiles) { foreach ($value in $workloads) { $cells.Add(@{ profile = $profileName; workload = $value }) } }
  } else {
    foreach ($profileName in $profiles) { $cells.Add(@{ profile = $profileName; workload = $Family }) }
  }
  return ,$cells.ToArray()
}

try {
  if (-not $DatasetCache) { $DatasetCache = Join-Path $repoRoot '.local-data/datasets/image-scroll/v1' }
  if ($FetchDataset) { $result = Receive-ImageScrollDataset $repoRoot $DatasetCache; $result | ConvertTo-Json -Depth 20 -Compress; exit 0 }
  if ($VerifyDataset) { $result = Test-ImageScrollCache $repoRoot $DatasetCache; $result | ConvertTo-Json -Depth 20 -Compress; exit 0 }
  if ($Rounds -lt 1 -or $Warmups -lt 0 -or $TimeoutSeconds -lt 1 -or $Width -lt 1 -or $Height -lt 1) {
    throw 'Rounds, timeout, and viewport dimensions must be positive; warmups cannot be negative'
  }
  if ($SigbusStress) {
    if ($Family -ne 'preparation') { throw '-SigbusStress requires -Family preparation' }
    $Profile = @('prepared-legacy', 'prepared-semaphore')
    $Rounds = 10; $Warmups = 0; $FailFast = $true
  }
  if (-not $RuntimeSource -or -not (Test-Path -LiteralPath $RuntimeSource -PathType Container)) {
    throw 'Set TOTALCROSS_SOURCE or pass -RuntimeSource to a clean TotalCross checkout'
  }
  if (-not $PackageManifest -or -not (Test-Path -LiteralPath $PackageManifest -PathType Leaf)) {
    throw 'Pass -PackageManifest pointing to the generated Windows package-manifest.json'
  }
  $RuntimeSource = [IO.Path]::GetFullPath($RuntimeSource)
  $PackageManifest = [IO.Path]::GetFullPath($PackageManifest)
  $DatasetCache = [IO.Path]::GetFullPath($DatasetCache)
  $script:activeFamily = $Family
  $script:runtimeCommit = Get-GitValue $RuntimeSource @('rev-parse', 'HEAD')
  if (Get-GitValue $RuntimeSource @('status', '--porcelain')) { throw 'TotalCross source checkout is dirty' }
  $script:benchmarkCommit = Get-GitValue $repoRoot @('rev-parse', 'HEAD')
  $benchmarkDirty = [bool](Get-GitValue $repoRoot @('status', '--porcelain'))
  $packageManifest = Assert-PackageManifest $PackageManifest $script:runtimeCommit $script:benchmarkCommit
  if ($packageManifest.benchmarkWorkingTreeDirty -or $benchmarkDirty) { throw 'Benchmark source must be clean for a packaged run' }
  if ($Family -in @('scroll', 'decode', 'preparation')) {
    $datasetCheck = Test-ImageScrollCache $repoRoot $DatasetCache
    $datasetInfo = [pscustomobject]@{
      id = $datasetCheck.id; version = $datasetCheck.version; manifestSha256 = $datasetCheck.manifestSha256
    }
  } else { $datasetInfo = $null }
  if ($datasetInfo -and $packageManifest.dataset.manifestSha256 -ne $datasetInfo.manifestSha256) {
    throw 'Package and verified dataset manifest identities differ'
  }
  $javaVersion = (& java -version 2>&1 | Select-Object -First 1)
  if (-not $javaVersion) { $javaVersion = 'unavailable' }
  $environment = [pscustomobject]@{
    hostOs = [Environment]::OSVersion.VersionString
    hostArchitecture = $(if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE })
    javaVersion = [string]$javaVersion
    totalcrossBuild = 'source:' + $script:runtimeCommit
    benchmarkWorkingTreeDirty = $benchmarkDirty
    hostName = [Environment]::MachineName
    sessionType = $(if ($env:SESSIONNAME -like 'RDP-*') { 'rdp' } else { $null })
  }
  if (-not $ResultsDirectory) { $ResultsDirectory = Join-Path $repoRoot 'results/image-rendering/windows' }
  [IO.Directory]::CreateDirectory($ResultsDirectory) | Out-Null
  $runRoot = Join-Path $ResultsDirectory ('run-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + $PID)
  [IO.Directory]::CreateDirectory($runRoot) | Out-Null
  $cells = Get-CellList
  $allRuns = New-Object 'System.Collections.Generic.List[object]'
  $failures = New-Object 'System.Collections.Generic.List[object]'
  $processIndex = 0
  foreach ($cell in $cells) {
    $profilePackage = $packageManifest.profiles.($cell.profile)
    $packageRoot = Split-Path -Parent $PackageManifest
    $executable = Join-Path $packageRoot $profilePackage.executable
    $workingDirectory = Join-Path $packageRoot $profilePackage.workingDirectory
    $runtimeFiles = @()
    foreach ($item in $profilePackage.runtimeFiles) {
      $path = Join-Path $packageRoot $item.path
      $runtimeFiles += [pscustomobject]@{ path = [IO.Path]::GetFullPath($path); sha256 = $item.sha256 }
    }
    $runtimeFiles += [pscustomobject]@{ path = [IO.Path]::GetFullPath($executable); sha256 = (Get-Hash $executable) }
    $runtimeFiles = @($runtimeFiles | Sort-Object path)
    $runtimeHash = [Security.Cryptography.SHA256]::Create()
    try {
      $hashInput = ConvertTo-Json -InputObject $runtimeFiles -Depth 5 -Compress
      $hashBytes = [Text.Encoding]::UTF8.GetBytes($hashInput)
      $runtimeIdentityHash = ([BitConverter]::ToString($runtimeHash.ComputeHash($hashBytes))).Replace('-', '').ToLowerInvariant()
    } finally { $runtimeHash.Dispose() }
    $runtimeIdentity = 'source:' + $script:runtimeCommit + ';artifact-sha256:' + $runtimeIdentityHash
    $baseConfig = New-BenchmarkConfig $cell 0 'preflight' $true $profilePackage $runtimeFiles $runtimeIdentity $environment $datasetInfo
    $processIndex++
    try {
      $preflightDir = Join-Path $runRoot ('preflight/' + $processIndex.ToString('D4') + '-' + $cell.profile + '-' + $cell.workload)
      $preflight = Invoke-BenchmarkChild $profilePackage $baseConfig $workingDirectory $preflightDir 'preflight' 0 $TimeoutSeconds
      if ($preflight.exitCode -ne 0) { throw 'Preflight did not exit cleanly' }
    } catch {
      $failures.Add([pscustomobject]@{ cell = $cell; phase = 'preflight'; round = 0; error = $_.Exception.Message })
      if ($FailFast) { break }
      continue
    }
    $cellRuns = New-Object 'System.Collections.Generic.List[object]'
    foreach ($phaseItem in @(@{ name = 'warmup'; count = $Warmups }, @{ name = 'measured'; count = $Rounds })) {
      for ($ordinal = 1; $ordinal -le $phaseItem.count; $ordinal++) {
        $processIndex++
        try {
          $config = New-BenchmarkConfig $cell $ordinal $phaseItem.name $false $profilePackage $runtimeFiles $runtimeIdentity $environment $datasetInfo
          $processDir = Join-Path $runRoot ('processes/' + $processIndex.ToString('D4') + '-' + $cell.profile + '-' + $phaseItem.name + '-' + $ordinal)
          $result = Invoke-BenchmarkChild $profilePackage $config $workingDirectory $processDir $phaseItem.name $ordinal $TimeoutSeconds
          $runRecord = $result.run
          if ($runRecord.profile -ne $cell.profile -or $runRecord.workload -ne $cell.workload -or
              $runRecord.runtimeSourceCommit -ne $script:runtimeCommit -or $runRecord.benchmarkSourceCommit -ne $script:benchmarkCommit) {
            throw 'Run provenance or requested cell identity does not match'
          }
          if ($datasetInfo) {
            if ($runRecord.dataset.id -ne $datasetInfo.id -or $runRecord.dataset.version -ne $datasetInfo.version -or
                $runRecord.dataset.manifestSha256 -ne $datasetInfo.manifestSha256) { throw 'Run dataset identity does not match the verified cache' }
          } elseif ($null -ne $runRecord.dataset) { throw 'Pacing run unexpectedly reports an image dataset' }
          foreach ($axis in @('source', 'scale', 'order')) {
            if ($cell.ContainsKey($axis) -and $runRecord.measurements.axes.$axis -ne $cell[$axis]) { throw "Run decode axis mismatch: $axis" }
          }
          $runRecord | Add-Member -NotePropertyName runnerWallTimeNs -NotePropertyValue $result.runnerWallTimeNs
          $runRecord | Add-Member -NotePropertyName runnerRuntimeFiles -NotePropertyValue $runtimeFiles
          $cellRuns.Add($runRecord)
          $allRuns.Add($runRecord)
        } catch {
          $failures.Add([pscustomobject]@{ cell = $cell; phase = $phaseItem.name; round = $ordinal; error = $_.Exception.Message })
          break
        }
      }
      if ($failures.Count -gt 0 -and $failures[$failures.Count - 1].cell.profile -eq $cell.profile -and
          $failures[$failures.Count - 1].cell.workload -eq $cell.workload) { break }
    }
    $measured = @($cellRuns | Where-Object { $_.phase -eq 'measured' })
    if ($measured.Count -gt 0) {
      $walls = @($measured | ForEach-Object { [double]$_.durationsNs.wallTime })
      $summary = [pscustomobject]@{
        schemaVersion = 1; recordType = 'summary'; family = $Family; workload = $cell.workload; profile = $cell.profile
        dataset = $datasetInfo; runtimeSourceCommit = $script:runtimeCommit; benchmarkSourceCommit = $script:benchmarkCommit
        rounds = $measured; failures = @($failures | Where-Object { $_.cell.profile -eq $cell.profile -and $_.cell.workload -eq $cell.workload }).Count
        statistics = [pscustomobject]@{ wallTimeNs = [pscustomobject]@{
          median = Get-Percentile $walls 0.50; p50 = Get-Percentile $walls 0.50; p95 = Get-Percentile $walls 0.95
          p99 = Get-Percentile $walls 0.99; max = ($walls | Measure-Object -Maximum).Maximum
        } }
        environment = $environment
      }
      $nameParts = @($cell.profile, $cell.workload)
      foreach ($axis in @('source', 'scale', 'order')) { if ($cell.ContainsKey($axis)) { $nameParts += $cell[$axis] } }
      [IO.File]::WriteAllText((Join-Path $runRoot (($nameParts -join '-') + '.summary.json')),
        (ConvertTo-Json -InputObject $summary -Depth 100), (New-Object System.Text.UTF8Encoding($false)))
    }
    if ($FailFast -and $failures.Count -gt 0) { break }
  }
  $runsPath = Join-Path $runRoot 'runs.jsonl'
  $lines = @($allRuns | ForEach-Object { ConvertTo-Json -InputObject $_ -Depth 100 -Compress })
  [IO.File]::WriteAllLines($runsPath, $lines, (New-Object System.Text.UTF8Encoding($false)))
  [IO.File]::WriteAllText((Join-Path $runRoot 'failures.json'), (ConvertTo-Json -InputObject @($failures) -Depth 50),
    (New-Object System.Text.UTF8Encoding($false)))
  [pscustomobject]@{ cells = $cells.Count; successfulRuns = $allRuns.Count; failures = $failures.Count; results = $runRoot } |
    ConvertTo-Json -Compress | Write-Output
  if ($failures.Count -gt 0) { exit 1 }
  exit 0
} catch {
  [Console]::Error.WriteLine($_.Exception.Message)
  exit 2
}
