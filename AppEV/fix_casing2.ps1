$screensPath = 'C:\PUBLIC CHARGER RND\AppEV\lib\screens'
$fixed = 0

Get-ChildItem -Path $screensPath -Filter '*.dart' | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $modified = $content
    $modified = $modified -creplace '\bforegroundcolor:', 'foregroundColor:'
    $modified = $modified -creplace '\btextcolor:', 'textColor:'
    $modified = $modified -creplace '\bbordercolor:', 'borderColor:'
    $modified = $modified -creplace '\biconcolor:', 'iconColor:'
    $modified = $modified -creplace '\bfillcolor:', 'fillColor:'
    $modified = $modified -creplace '\bhintcolor:', 'hintColor:'
    if ($modified -ne $content) {
        Set-Content $_.FullName $modified -NoNewline
        $fixed++
        Write-Host "Fixed: $($_.Name)"
    }
}
Write-Host "Total: $fixed files"
