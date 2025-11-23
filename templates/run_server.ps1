# PowerShell helper to run the Flask server from the template folder
$cwd = "c:\Users\SONIYA\OneDrive\Desktop\MMMEC AI AGENT\template"
Push-Location $cwd
Write-Host "Starting server in $cwd"
# Use Start-Process to run in new window; change -NoNewWindow to $true to run in same window
Start-Process -FilePath python -ArgumentList "server.py" -WorkingDirectory $cwd
Pop-Location
Write-Host "Server started (check processes)."