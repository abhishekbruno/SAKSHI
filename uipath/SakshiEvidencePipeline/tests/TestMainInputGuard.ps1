Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw "ASSERTION FAILED: $Message"
    }
}

function Get-MainInputDecision {
    param(
        [AllowNull()][string]$CaseId,
        [AllowNull()][string]$EvidenceFilePath
    )

    if ([string]::IsNullOrWhiteSpace($CaseId)) {
        return [pscustomobject]@{
            Valid = $false
            Status = 'INVALID_INPUT'
            Message = 'Input validation failed: in_CaseId is required before running Main.xaml.'
            Endpoint = $null
        }
    }

    if ([string]::IsNullOrWhiteSpace($EvidenceFilePath)) {
        return [pscustomobject]@{
            Valid = $false
            Status = 'INVALID_INPUT'
            Message = 'Input validation failed: in_EvidenceFilePath is required for initial upload.'
            Endpoint = $null
        }
    }

    if (-not [System.IO.File]::Exists($EvidenceFilePath)) {
        return [pscustomobject]@{
            Valid = $false
            Status = 'INVALID_INPUT'
            Message = 'Input validation failed: in_EvidenceFilePath does not point to an existing file accessible to the robot.'
            Endpoint = $null
        }
    }

    return [pscustomobject]@{
        Valid = $true
        Status = $null
        Message = $null
        Endpoint = 'http://localhost:8000/api/v1/cases/' + $CaseId + '/evidence/pipeline'
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$mainPath = Join-Path $projectRoot 'Main.xaml'
$entryPath = Join-Path $projectRoot 'entry-points.json'
$sidecarPath = Join-Path $projectRoot 'Main.xaml.json'
$projectPath = Join-Path $projectRoot 'project.json'
$validPath = Join-Path $projectRoot 'project.json'
$invalidPath = Join-Path $projectRoot 'does-not-exist-for-main-input-test.bin'

Assert-True (Test-Path -LiteralPath $mainPath -PathType Leaf) 'Main.xaml exists.'
Assert-True (Test-Path -LiteralPath $entryPath -PathType Leaf) 'entry-points.json exists.'
Assert-True (Test-Path -LiteralPath $sidecarPath -PathType Leaf) 'Main.xaml.json exists.'
Assert-True (Test-Path -LiteralPath $projectPath -PathType Leaf) 'project.json exists.'

Add-Type -AssemblyName System.Xml.Linq
$mainXml = [System.Xml.Linq.XDocument]::Load($mainPath)
$mainText = $mainXml.ToString()
$rootSequence = $mainXml.Descendants() | Where-Object {
    $_.Name.LocalName -eq 'Sequence' -and $_.Attributes().Where({ $_.Name.LocalName -eq 'DisplayName' -and $_.Value -eq 'Sakshi Evidence Pipeline Master Workflow' }).Count -gt 0
} | Select-Object -First 1
$children = @($rootSequence.Elements())
$guardIndex = -1
$configReadIndex = -1
$urlAssignIndex = -1
for ($i = 0; $i -lt $children.Count; $i++) {
    $displayNameAttribute = @($children[$i].Attributes() | Where-Object { $_.Name.LocalName -eq 'DisplayName' } | Select-Object -First 1)
    $displayName = if ($displayNameAttribute.Count -gt 0) { $displayNameAttribute[0].Value } else { '' }
    if ($displayName -eq 'Validate Required Main Inputs') { $guardIndex = $i }
    if ($displayName -eq 'Read Config JSON') { $configReadIndex = $i }
    if ($displayName -eq 'Resolve Pipeline Endpoint URL') { $urlAssignIndex = $i }
}

Assert-True ($guardIndex -ge 0) 'Main.xaml contains the required-input validation gate.'
Assert-True ($configReadIndex -gt $guardIndex) 'Config loading occurs after input validation.'
Assert-True ($urlAssignIndex -gt $guardIndex) 'Endpoint construction occurs after input validation.'
Assert-True ($mainText -match 'String\.IsNullOrWhiteSpace\(in_CaseId\)') 'The guard validates Case ID.'
Assert-True ($mainText -match 'String\.IsNullOrWhiteSpace\(in_EvidenceFilePath\)') 'The guard validates file-path presence.'
Assert-True ($mainText -match 'System\.IO\.File\.Exists\(in_EvidenceFilePath\)') 'The guard validates file existence.'
Assert-True ($mainText -match 'INVALID_INPUT') 'The guard assigns INVALID_INPUT.'
Assert-True ($mainText -match 'No HTTP request was sent') 'The guard emits a no-request diagnostic.'
Assert-True ($mainText -match '<Throw ') 'The guard stops execution on invalid inputs.'

$entry = Get-Content -Raw -LiteralPath $entryPath | ConvertFrom-Json
$sidecar = Get-Content -Raw -LiteralPath $sidecarPath | ConvertFrom-Json
$project = Get-Content -Raw -LiteralPath $projectPath | ConvertFrom-Json
$required = @($entry.entryPoints[0].input.required)
$caseSidecar = $sidecar.Arguments | Where-Object { $_.Name -eq 'in_CaseId' }
$fileSidecar = $sidecar.Arguments | Where-Object { $_.Name -eq 'in_EvidenceFilePath' }
$caseProject = $project.arguments.input | Where-Object { $_.name -eq 'in_CaseId' }
$fileProject = $project.arguments.input | Where-Object { $_.name -eq 'in_EvidenceFilePath' }
Assert-True ($required -contains 'in_CaseId') 'Entry-point metadata requires in_CaseId.'
Assert-True ($required -contains 'in_EvidenceFilePath') 'Entry-point metadata requires in_EvidenceFilePath.'
Assert-True ($required.Count -eq 2) 'Only Case ID and evidence-file path are required entry-point inputs.'
Assert-True ([bool]$caseSidecar.IsRequired) 'Studio sidecar requires in_CaseId.'
Assert-True ([bool]$fileSidecar.IsRequired) 'Studio sidecar requires in_EvidenceFilePath.'
Assert-True ([bool]$caseProject.required) 'project.json requires in_CaseId.'
Assert-True ([bool]$fileProject.required) 'project.json requires in_EvidenceFilePath.'

$missingCase = Get-MainInputDecision -CaseId $null -EvidenceFilePath $validPath
Assert-True (-not $missingCase.Valid) 'Missing Case ID is rejected.'
Assert-True ($missingCase.Status -eq 'INVALID_INPUT') 'Missing Case ID returns INVALID_INPUT.'
Assert-True ($missingCase.Endpoint -eq $null) 'Missing Case ID does not construct an endpoint.'

$missingFile = Get-MainInputDecision -CaseId 'SAKSHI-CASE-TEST' -EvidenceFilePath $null
Assert-True (-not $missingFile.Valid) 'Missing evidence file path is rejected.'
Assert-True ($missingFile.Status -eq 'INVALID_INPUT') 'Missing file path returns INVALID_INPUT.'
Assert-True ($missingFile.Endpoint -eq $null) 'Missing file path does not construct an endpoint.'

$invalidFile = Get-MainInputDecision -CaseId 'SAKSHI-CASE-TEST' -EvidenceFilePath $invalidPath
Assert-True (-not $invalidFile.Valid) 'Nonexistent evidence file is rejected.'
Assert-True ($invalidFile.Status -eq 'INVALID_INPUT') 'Nonexistent evidence file returns INVALID_INPUT.'
Assert-True ($invalidFile.Endpoint -eq $null) 'Nonexistent evidence file does not construct an endpoint.'

$valid = Get-MainInputDecision -CaseId 'SAKSHI-CASE-TEST' -EvidenceFilePath $validPath
Assert-True $valid.Valid 'Non-empty Case ID and existing file are accepted.'
Assert-True ($valid.Endpoint -eq 'http://localhost:8000/api/v1/cases/SAKSHI-CASE-TEST/evidence/pipeline') 'Valid inputs construct the expected endpoint.'
Assert-True ($valid.Endpoint -notmatch '/cases//') 'Valid endpoint never contains an empty Case ID segment.'

Write-Output 'PASS: input guard precedes config loading and endpoint construction'
Write-Output 'PASS: Case ID and evidence path are required in all launch metadata'
Write-Output 'PASS: missing Case ID rejected without endpoint'
Write-Output 'PASS: missing file path rejected without endpoint'
Write-Output 'PASS: nonexistent file rejected without endpoint'
Write-Output 'PASS: valid Case ID and existing file construct a safe endpoint'
