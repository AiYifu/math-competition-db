# PowerShell script to run all 3 books in background

$logsDir = "E:\数学竞赛helper\竞赛helper\logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

Write-Host "Starting 3 book extractions..."
Write-Host ""

# Book 1: secret2
Write-Host "Starting secret2..."
Start-Process -FilePath "python" `
    -ArgumentList "extract_concurrent.py --book secret2 --workers 1 --chunk-size 8 --resume --sleep 60" `
    -NoNewWindow `
    -WorkingDirectory "E:\数学竞赛helper\竞赛helper" `
    -RedirectStandardOutput "$logsDir\secret2_pipe.log" `
    -RedirectStandardError "$logsDir\secret2_pipe_err.log"

# Book 2: tip4
Write-Host "Starting tip4..."
Start-Process -FilePath "python" `
    -ArgumentList "extract_concurrent.py --book tip4 --workers 1 --chunk-size 8 --resume --sleep 60" `
    -NoNewWindow `
    -WorkingDirectory "E:\数学竞赛helper\竞赛helper" `
    -RedirectStandardOutput "$logsDir\tip4_pipe.log" `
    -RedirectStandardError "$logsDir\tip4_pipe_err.log"

# Book 3: tip9
Write-Host "Starting tip9..."
Start-Process -FilePath "python" `
    -ArgumentList "extract_concurrent.py --book tip9 --workers 1 --chunk-size 8 --resume --sleep 60" `
    -NoNewWindow `
    -WorkingDirectory "E:\数学竞赛helper\竞赛helper" `
    -RedirectStandardOutput "$logsDir\tip9_pipe.log" `
    -RedirectStandardError "$logsDir\tip9_pipe_err.log"

Write-Host ""
Write-Host "All 3 books started!"
Write-Host ""
Write-Host "Monitor progress:"
Write-Host "  Get-Content logs\secret2_pipe.log -Tail 10"
Write-Host "  Get-Content logs\tip4_pipe.log -Tail 10"
Write-Host "  Get-Content logs\tip9_pipe.log -Tail 10"
Write-Host ""
Write-Host "Check counts:"
Write-Host '  (Get-ChildItem output\secret2\problems\*.json).Count'
Write-Host '  (Get-ChildItem output\tip4\problems\*.json).Count'
Write-Host '  (Get-ChildItem output\tip9\problems\*.json).Count'
