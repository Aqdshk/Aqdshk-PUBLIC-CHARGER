$excludeFiles = @('ev_illustration.dart', 'splash_screen.dart', 'profile_screen.dart')
$targetDirs = @('C:\PUBLIC CHARGER RND\AppEV\lib\screens', 'C:\PUBLIC CHARGER RND\AppEV\lib\widgets')
$fixed = 0
Get-ChildItem -Path $targetDirs -Filter '*.dart' | Where-Object { $excludeFiles -notcontains $_.Name } | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $modified = $content -replace 'color: Colors\.white(?=[,\s\n)])', 'color: AppColors.textPrimary'
    if ($modified -ne $content) {
        if ($modified -notmatch 'app_colors') {
            $firstImport = "import 'package:flutter/material.dart';"
            $modified = $modified.Replace($firstImport, $firstImport + "`nimport '../constants/app_colors.dart';")
        }
        Set-Content $_.FullName $modified -NoNewline
        $fixed++
        Write-Host "Fixed: $($_.Name)"
    }
}
Write-Host "Total: $fixed files"
