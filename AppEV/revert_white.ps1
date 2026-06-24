
# Revert Colors.white -> AppColors.textPrimary changes back to Colors.white
# Keep the hex -> AppColors background replacements

$targetDirs = @('C:\PUBLIC CHARGER RND\AppEV\lib\screens', 'C:\PUBLIC CHARGER RND\AppEV\lib\widgets')
$fixed = 0

Get-ChildItem -Path $targetDirs -Filter '*.dart' | Where-Object { $_.Name -ne 'ev_illustration.dart' } | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $modified = $content
    # Revert only the Colors.white -> textPrimary changes in color: property
    $modified = $modified -replace 'color: AppColors\.textPrimary(?=[,\s\n)])', 'color: Colors.white'
    # But keep foregroundColor: AppColors.textPrimary as is (those are buttons where we want theme)
    if ($modified -ne $content) {
        Set-Content $_.FullName $modified -NoNewline
        $fixed++
        Write-Host "Reverted: $($_.Name)"
    }
}
Write-Host "Total reverted: $fixed files"
