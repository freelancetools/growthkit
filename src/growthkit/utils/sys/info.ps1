# Save this as system_info.ps1

Write-Output "- Operating System"
$os = Get-CimInstance Win32_OperatingSystem
Write-Output "OS Name:         $($os.Caption)"
Write-Output "Version:         $($os.Version)"
Write-Output "Build:           $($os.BuildNumber)"

Write-Output "`n- Environment"
Write-Output "PowerShell:      $($PSVersionTable.PSVersion)"
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonVersion = (python --version 2>&1).ToString().Split()[1]
    Write-Output "Python:          $pythonVersion"
}
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVersion = (git --version 2>&1).ToString().Split()[2]
    Write-Output "Git:             $gitVersion"
}
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVersion = (node --version 2>&1).ToString().Trim("v")
    Write-Output "Node.js:         $nodeVersion"
}