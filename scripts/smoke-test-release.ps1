param(
  [string]$MoshuExe = "",
  [string]$ProjectId = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Step {
  param([string]$Message)
  Write-Host "[smoke] $Message" -ForegroundColor Cyan
}

function Write-Pass {
  param([string]$Message)
  Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Write-Fail {
  param([string]$Message)
  Write-Host "[FAIL] $Message" -ForegroundColor Red
}

# Find Moshu.exe
$scriptDir = Split-Path -Parent $MyInvocation.ScriptName
$repoRoot = Split-Path -Parent $scriptDir

if (-not $MoshuExe) {
  $candidates = @(
    (Join-Path $repoRoot "release\Moshu.exe"),
    (Join-Path $repoRoot "release\NovelWritingAgent.exe")
  )
  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) {
      $MoshuExe = $candidate
      break
    }
  }
}

if (-not $MoshuExe -or -not (Test-Path -LiteralPath $MoshuExe)) {
  Write-Fail "Moshu.exe not found. Run build-exe.bat first."
  exit 1
}

Write-Step "Using Moshu.exe: $MoshuExe"

# Step 1: Verify MCP entrypoint works
Write-Step "Step 1: Verify MCP entrypoint..."
$mcpArgs = @("--mcp-server", "--help")
if ($DryRun) {
  Write-Step "Dry run: would run $MoshuExe $($mcpArgs -join ' ')"
} else {
  $output = & $MoshuExe @mcpArgs 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Fail "MCP entrypoint failed with exit code $LASTEXITCODE"
    exit 1
  }
  Write-Pass "MCP entrypoint works"
}

# Step 2: Verify auto permission pack
Write-Step "Step 2: Verify auto permission pack..."
$mcpArgs = @("--mcp-server", "--permission-pack", "auto", "--help")
if ($DryRun) {
  Write-Step "Dry run: would run $MoshuExe $($mcpArgs -join ' ')"
} else {
  $output = & $MoshuExe @mcpArgs 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Fail "Auto permission pack failed with exit code $LASTEXITCODE"
    exit 1
  }
  Write-Pass "Auto permission pack works"
}

# Step 3: Verify setup script exists
Write-Step "Step 3: Verify setup script..."
$setupScript = Join-Path $repoRoot "scripts\setup-external-agent-mcp.ps1"
if (Test-Path -LiteralPath $setupScript) {
  Write-Pass "Setup script found: $setupScript"
} else {
  Write-Fail "Setup script not found"
  exit 1
}

# Step 4: Verify docs exist
Write-Step "Step 4: Verify docs..."
$docs = @(
  (Join-Path $repoRoot "docs\mcp\claude-code-codex-client.md"),
  (Join-Path $repoRoot "docs\agent\external-no-api-cataloging.md"),
  (Join-Path $repoRoot "docs\agent\external-agent-cataloging-permissions-task-board.md")
)
foreach ($doc in $docs) {
  if (Test-Path -LiteralPath $doc) {
    Write-Pass "Doc found: $(Split-Path -Leaf $doc)"
  } else {
    Write-Fail "Doc not found: $(Split-Path -Leaf $doc)"
    exit 1
  }
}

# Step 5: Run backend tests
Write-Step "Step 5: Run backend tests..."
if ($DryRun) {
  Write-Step "Dry run: would run pytest"
} else {
  Push-Location (Join-Path $repoRoot "backend")
  try {
    py -m pytest tests/test_external_cataloging_tools.py tests/test_external_cataloging_apply.py tests/test_agent_external_cataloging_plan.py tests/test_prompt_packs_external_cataloging.py -q
    if ($LASTEXITCODE -ne 0) {
      Write-Fail "Backend tests failed"
      exit 1
    }
    Write-Pass "Backend tests passed"
  } finally {
    Pop-Location
  }
}

Write-Step ""
Write-Pass "All smoke tests passed!"
