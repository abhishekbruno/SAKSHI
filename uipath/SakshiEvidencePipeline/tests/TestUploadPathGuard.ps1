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

function Get-InitialUploadDecision {
    param([AllowNull()][string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or -not [System.IO.File]::Exists($Path)) {
        if ([string]::IsNullOrWhiteSpace($Path)) {
            return [pscustomobject]@{
                Action = 'Reject'
                StatusCode = 400
                Message = 'Evidence file path is required for initial upload.'
                AttachmentPath = $null
                Attachments = @{}
            }
        }

        return [pscustomobject]@{
            Action = 'Reject'
            StatusCode = 400
            Message = 'Evidence file path does not identify an existing file accessible to the robot.'
            AttachmentPath = $null
            Attachments = @{}
        }
    }

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    return [pscustomobject]@{
        Action = 'Upload'
        StatusCode = $null
        Message = $null
        AttachmentPath = $fullPath
        Attachments = @{ file = $fullPath }
    }
}

function Get-SubmissionDecision {
    param(
        [AllowNull()][string]$EvidenceId,
        [AllowNull()][string]$Path
    )

    if (-not [string]::IsNullOrEmpty($EvidenceId)) {
        return [pscustomobject]@{
            Action = 'Resume'
            Attachments = @{}
            EvidenceId = $EvidenceId
        }
    }

    $initial = Get-InitialUploadDecision -Path $Path
    return [pscustomobject]@{
        Action = $initial.Action
        StatusCode = $initial.StatusCode
        Message = $initial.Message
        Attachments = if ($initial.Action -eq 'Upload') { @{ file = $initial.AttachmentPath } } else { @{} }
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$submitPath = Join-Path $projectRoot 'SubmitEvidencePipeline.xaml'
$responsePath = Join-Path $projectRoot 'ProcessPipelineResponse.xaml'
$mainPath = Join-Path $projectRoot 'Main.xaml'
$validPath = Join-Path $projectRoot 'project.json'
$invalidPath = Join-Path $projectRoot 'does-not-exist-for-upload-test.bin'

Assert-True (Test-Path -LiteralPath $submitPath) 'SubmitEvidencePipeline.xaml exists.'
Assert-True (Test-Path -LiteralPath $responsePath) 'ProcessPipelineResponse.xaml exists.'
Assert-True (Test-Path -LiteralPath $mainPath) 'Main.xaml exists.'
Assert-True (Test-Path -LiteralPath $validPath -PathType Leaf) 'The valid test file exists.'

Add-Type -AssemblyName System.Xml.Linq
$submitXml = [System.Xml.Linq.XDocument]::Load($submitPath)
$responseXml = [System.Xml.Linq.XDocument]::Load($responsePath)
$mainXml = [System.Xml.Linq.XDocument]::Load($mainPath)

$validationIf = @($submitXml.Descendants() | Where-Object {
    $_.Name.LocalName -eq 'If' -and $_.Attributes().Where({ $_.Name.LocalName -eq 'DisplayName' -and $_.Value -eq 'Validate Initial Evidence File Path' }).Count -gt 0
})
Assert-True ($validationIf.Count -eq 1) 'The initial upload has exactly one file-path validation branch.'
$validationCondition = ($validationIf[0].Attributes() | Where-Object { $_.Name.LocalName -eq 'Condition' }).Value
Assert-True ($validationCondition -match 'String\.IsNullOrWhiteSpace\(in_EvidenceFilePath\)') 'The validation checks for a missing or blank path.'
Assert-True ($validationCondition -match 'System\.IO\.File\.Exists\(in_EvidenceFilePath\)') 'The validation checks that the file exists.'

$upload = @($submitXml.Descendants() | Where-Object {
    $_.Name.LocalName -eq 'HttpClient' -and $_.Attributes().Where({ $_.Name.LocalName -eq 'DisplayName' -and $_.Value -eq 'HTTP Pipeline Upload Request' }).Count -gt 0
})
$resume = @($submitXml.Descendants() | Where-Object {
    $_.Name.LocalName -eq 'HttpClient' -and $_.Attributes().Where({ $_.Name.LocalName -eq 'DisplayName' -and $_.Value -eq 'HTTP Pipeline Resume Request' }).Count -gt 0
})
Assert-True ($upload.Count -eq 1) 'Exactly one initial upload HTTP activity exists.'
Assert-True ($resume.Count -eq 1) 'Exactly one resume HTTP activity exists.'
Assert-True ($upload[0].ToString() -match 'x:Key="file"') 'The upload attachment field is named file.'
Assert-True ($upload[0].ToString() -match 'validatedEvidenceFilePath') 'The upload uses the validated full path.'
Assert-True (-not ($resume[0].ToString() -match 'x:Key="file"')) 'The resume request has no file attachment.'
Assert-True ($resume[0].ToString() -match 'x:Key="evidence_id"') 'The resume request sends evidence_id.'
Assert-True ($responseXml.ToString() -match 'Handle 400 Invalid Intake Request') 'The response processor handles local 400 input failures.'
Assert-True ($responseXml.ToString() -match 'INTAKE_FAILED') 'The response processor preserves the intake-failure status.'
Assert-True ($mainXml.ToString() -match 'x:Key="in_EvidenceFilePath">\[in_EvidenceFilePath\]') 'Main maps the file path into the child workflow.'

$missing = Get-InitialUploadDecision -Path $null
Assert-True ($missing.Action -eq 'Reject') 'Missing path is rejected before HTTP.'
Assert-True ($missing.StatusCode -eq 400) 'Missing path returns local 400.'
Assert-True ($missing.Attachments.Count -eq 0) 'Missing path has no attachment.'

$blank = Get-InitialUploadDecision -Path '   '
Assert-True ($blank.Action -eq 'Reject') 'Whitespace path is rejected before HTTP.'
Assert-True ($blank.StatusCode -eq 400) 'Whitespace path returns local 400.'

$invalid = Get-InitialUploadDecision -Path $invalidPath
Assert-True ($invalid.Action -eq 'Reject') 'Nonexistent path is rejected before HTTP.'
Assert-True ($invalid.StatusCode -eq 400) 'Nonexistent path returns local 400.'

$valid = Get-InitialUploadDecision -Path $validPath
Assert-True ($valid.Action -eq 'Upload') 'Existing file path is accepted for upload.'
Assert-True ([System.IO.Path]::IsPathRooted($valid.AttachmentPath) -and $valid.AttachmentPath -eq [System.IO.Path]::GetFullPath($valid.AttachmentPath)) 'Accepted upload path is normalized to a full path.'
Assert-True ([System.IO.File]::Exists($valid.AttachmentPath)) 'Accepted upload path still resolves to an existing file.'

$resumeDecision = Get-SubmissionDecision -EvidenceId 'SAKSHI-EVID-TEST-RESUME' -Path $invalidPath
Assert-True ($resumeDecision.Action -eq 'Resume') 'Resume input selects the resume branch.'
Assert-True ($resumeDecision.Attachments.Count -eq 0) 'Resume input sends no attachment even when the file path is invalid.'
Assert-True ($resumeDecision.EvidenceId -eq 'SAKSHI-EVID-TEST-RESUME') 'Resume preserves the evidence ID.'

Write-Output 'PASS: missing path rejected without upload'
Write-Output 'PASS: blank path rejected without upload'
Write-Output 'PASS: nonexistent path rejected without upload'
Write-Output 'PASS: existing path normalized and attached as file'
Write-Output 'PASS: resume path sends evidence_id with no attachment'
Write-Output 'PASS: XAML structure and binding assertions'
