$required = @("requirements.md", "architecture.md", "design-review.md", "impl-plan.md", "review.md", "verify.md")
$missing = @()

foreach ($file in $required) {
    if (-not (Test-Path $file)) {
        $missing += $file
    }
}

if ($missing.Count -gt 0) {
    Write-Error "Pre-PR Hook Failed: Missing SDLC files: $($missing -join ', ')"
    exit 1
} else {
    Write-Host "All SDLC artifacts present. Ready for PR generation." -ForegroundColor Green
}
