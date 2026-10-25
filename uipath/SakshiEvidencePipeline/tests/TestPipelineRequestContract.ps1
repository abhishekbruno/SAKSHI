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

$projectRoot = Split-Path -Parent $PSScriptRoot
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $projectRoot)
$mainPath = Join-Path $projectRoot 'Main.xaml'
$submitPath = Join-Path $projectRoot 'SubmitEvidencePipeline.xaml'
$responsePath = Join-Path $projectRoot 'ProcessPipelineResponse.xaml'
$configPath = Join-Path $projectRoot 'Config.json'
$routePath = Join-Path $repositoryRoot 'backend/app/api/v1/evidence.py'

foreach ($path in @($mainPath, $submitPath, $responsePath, $configPath, $routePath)) {
    Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "Required contract source exists: $path"
}

Add-Type -AssemblyName System.Xml.Linq
$mainXml = [System.Xml.Linq.XDocument]::Load($mainPath)
$submitXml = [System.Xml.Linq.XDocument]::Load($submitPath)
$mainText = $mainXml.ToString()
$submitText = $submitXml.ToString()
$responseText = ([System.Xml.Linq.XDocument]::Load($responsePath)).ToString()
$routeText = Get-Content -Raw -LiteralPath $routePath
$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json

# The checked-in configuration is intentionally unusable for authentication.
Assert-True ($config.Settings.AuthenticationMode -eq 'not-configured') 'Checked-in configuration fails closed until a local authentication mode is chosen.'
Assert-True ([string]::IsNullOrWhiteSpace($config.Settings.DevelopmentInvestigatorId)) 'Checked-in configuration contains no development investigator ID.'
Assert-True ([string]::IsNullOrWhiteSpace($config.Settings.DevelopmentInvestigatorRole)) 'Checked-in configuration contains no development role.'
Assert-True ([string]::IsNullOrWhiteSpace($config.Settings.DevelopmentInvestigatorJurisdiction)) 'Checked-in configuration contains no development jurisdiction.'

# Main must reject anything other than explicit development authentication before URL construction.
$rootSequence = $mainXml.Descendants() | Where-Object {
    $_.Name.LocalName -eq 'Sequence' -and $_.Attributes().Where({ $_.Name.LocalName -eq 'DisplayName' -and $_.Value -eq 'Sakshi Evidence Pipeline Master Workflow' }).Count -gt 0
} | Select-Object -First 1
$children = @($rootSequence.Elements())
$rejectAuthIndex = -1
$identityGateIndex = -1
$endpointIndex = -1
for ($i = 0; $i -lt $children.Count; $i++) {
    $displayNameAttribute = @($children[$i].Attributes() | Where-Object { $_.Name.LocalName -eq 'DisplayName' } | Select-Object -First 1)
    $displayName = if ($displayNameAttribute.Count -gt 0) { $displayNameAttribute[0].Value } else { '' }
    if ($displayName -eq 'Reject Unsupported Authentication Mode') { $rejectAuthIndex = $i }
    if ($displayName -eq 'Require Explicit Development Identity') { $identityGateIndex = $i }
    if ($displayName -eq 'Resolve Pipeline Endpoint URL') { $endpointIndex = $i }
}

Assert-True ($mainText -match 'AuthenticationMode') 'Main reads the configured authentication mode.'
Assert-True ($mainText -match 'AUTHENTICATION_CONFIGURATION_REQUIRED') 'Main returns a safe configuration status when authentication is unavailable.'
Assert-True ($rejectAuthIndex -ge 0 -and $rejectAuthIndex -lt $endpointIndex) 'Unsupported authentication is rejected before endpoint construction.'
Assert-True ($identityGateIndex -ge 0 -and $identityGateIndex -lt $endpointIndex) 'Incomplete development identity is rejected before endpoint construction.'
Assert-True ($mainText -match 'x:Key="in_InvestigatorRole">\[investigatorRole\]') 'Main passes the configured development role to new-upload requests.'
Assert-True ($mainText -match 'x:Key="in_InvestigatorJurisdiction">\[investigatorJurisdiction\]') 'Main passes the configured development jurisdiction to child requests.'

# Both HTTP branches must use only arguments supplied by Main; no identity fallback belongs in source.
Assert-True ($submitText -notmatch 'IO-7842-SHARMA|JUR-DEL-04') 'Submit workflow contains no hardcoded development identity.'
Assert-True ($submitText -notmatch 'Bearer\s') 'Submit workflow does not embed a bearer token.'
Assert-True ($submitText -match 'x:Key="X-Investigator-Id">\[in_InvestigatorId\]') 'Development investigator ID is supplied by Main.'
Assert-True ($submitText -match 'x:Key="X-Investigator-Role">\[in_InvestigatorRole\]') 'Development role is supplied by Main.'
Assert-True ($submitText -match 'x:Key="X-Investigator-Jurisdiction">\[in_InvestigatorJurisdiction\]') 'Development jurisdiction is supplied by Main.'

$upload = @($submitXml.Descendants() | Where-Object {
    $_.Name.LocalName -eq 'HttpClient' -and $_.Attributes().Where({ $_.Name.LocalName -eq 'DisplayName' -and $_.Value -eq 'HTTP Pipeline Upload Request' }).Count -gt 0
})
$resume = @($submitXml.Descendants() | Where-Object {
    $_.Name.LocalName -eq 'HttpClient' -and $_.Attributes().Where({ $_.Name.LocalName -eq 'DisplayName' -and $_.Value -eq 'HTTP Pipeline Resume Request' }).Count -gt 0
})
Assert-True ($upload.Count -eq 1 -and $upload[0].Attribute('Method').Value -eq 'POST') 'Initial pipeline request is a single POST.'
Assert-True ($upload[0].ToString() -match 'x:Key="file"') 'Initial pipeline request uses multipart attachment field file.'
Assert-True ($upload[0].ToString() -match 'x:Key="evidence_category"') 'Initial pipeline request supplies evidence_category.'
Assert-True ($upload[0].ToString() -match 'x:Key="declared_mime_type"') 'Initial pipeline request supplies declared_mime_type.'
Assert-True ($resume.Count -eq 1 -and $resume[0].Attribute('Method').Value -eq 'POST') 'Resume request is a single POST.'
Assert-True ($resume[0].ToString() -match 'x:Key="evidence_id"') 'Resume request supplies evidence_id.'
Assert-True (-not ($resume[0].ToString() -match 'x:Key="file"')) 'Resume request sends no second evidence file.'
Assert-True ($responseText -match 'in_StatusCode = 503') 'Response processing identifies retryable 503 responses.'
Assert-True ($responseText -match 'in_StatusCode = 401') 'Response processing identifies terminal 401 responses.'
Assert-True ($responseText -match 'in_StatusCode = 403') 'Response processing identifies terminal 403 responses.'

# Keep the XAML request names synchronized with the FastAPI route contract.
Assert-True ($routeText -match '@router\.post\(\s*"/pipeline"') 'FastAPI exposes the composite pipeline POST route.'
Assert-True ($routeText -match 'file: Optional\[UploadFile\] = File') 'FastAPI expects the multipart file field.'
Assert-True ($routeText -match 'evidence_id: Optional\[str\] = Form') 'FastAPI accepts evidence_id for resume.'
Assert-True ($routeText -match 'evidence_category: Optional\[EvidenceCategory\] = Form') 'FastAPI expects evidence_category for a new upload.'
Assert-True ($routeText -match 'declared_mime_type: Optional\[str\] = Form') 'FastAPI expects declared_mime_type for a new upload.'
Assert-True ($routeText -match 'A resume request accepts only') 'FastAPI documents resume-only safety.'
Assert-True ($routeText -match 'status\.HTTP_201_CREATED') 'FastAPI maps a successful initial upload to 201.'
Assert-True ($routeText -match 'status\.HTTP_200_OK if is_resume') 'FastAPI maps a successful resume to 200.'
Assert-True ($routeText -match 'status\.HTTP_422_UNPROCESSABLE_ENTITY') 'FastAPI maps validation or quarantine outcomes to 422.'
Assert-True ($routeText -match 'status\.HTTP_503_SERVICE_UNAVAILABLE') 'FastAPI maps retryable operational outcomes to 503.'

Write-Output 'PASS: checked-in UiPath authentication configuration fails closed'
Write-Output 'PASS: development identity is explicit and never hardcoded in HTTP requests'
Write-Output 'PASS: XAML multipart and resume requests match the FastAPI pipeline contract'
Write-Output 'PASS: terminal and retryable response classifications are present'
