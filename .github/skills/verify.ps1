Write-Host "=== Running Pytest Verification Suite ===" -ForegroundColor Cyan
pytest tests/unit tests/integration -v --cov=.

Write-Host "=== Checking Documentation Artifacts ===" -ForegroundColor Cyan
$requiredDocs = @("requirements.md", "architecture.md", "design-review.md", "impl-plan.md")
foreach ($doc in $requiredDocs) {
    if (Test-Path $doc) {
        Write-Host "[OK] $doc exists" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] $doc not found" -ForegroundColor Red
    }
}
