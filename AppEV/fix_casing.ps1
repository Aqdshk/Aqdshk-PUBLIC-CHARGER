$targetDirs = @('C:\PUBLIC CHARGER RND\AppEV\lib\screens', 'C:\PUBLIC CHARGER RND\AppEV\lib\widgets')
$dynamicGetters = 'textPrimary|textSecondary|textTertiary|textLight|background|surface|cardBackground|borderLight|accentGreen|glassBackground|glassBorder'
$fixed = 0

Get-ChildItem -Path $targetDirs -Filter '*.dart' | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $modified = $content

    # Fix broken parameter names from case-insensitive replacement
    $modified = $modified -replace '\bforegroundcolor:', 'foregroundColor:'
    $modified = $modified -replace '\btextcolor:', 'textColor:'
    $modified = $modified -replace '\bbordercolor:', 'borderColor:'
    $modified = $modified -replace '\bbuttoncolor:', 'buttonColor:'
    $modified = $modified -replace '\bhintcolor:', 'hintColor:'
    $modified = $modified -replace '\biconcolor:', 'iconColor:'
    $modified = $modified -replace '\bfillcolor:', 'fillColor:'
    $modified = $modified -replace '\bhighlightcolor:', 'highlightColor:'
    $modified = $modified -replace '\bsplashcolor:', 'splashColor:'
    $modified = $modified -replace '\boverlaycolor:', 'overlayColor:'
    $modified = $modified -replace '\bindicatorcolor:', 'indicatorColor:'
    $modified = $modified -replace '\blabelcolor:', 'labelColor:'
    $modified = $modified -replace '\bunselectedlabelcolor:', 'unselectedLabelColor:'
    $modified = $modified -replace '\bselectcolor:', 'selectColor:'
    $modified = $modified -replace '\bcursorcolor:', 'cursorColor:'
    $modified = $modified -replace '\bbarriercolor:', 'barrierColor:'

    # Remove const from newly non-const TextStyle/widgets using AppColors
    if ($modified -match "AppColors\.($dynamicGetters)") {
        $modified = $modified -replace '\bconst TextStyle\(', 'TextStyle('
        $modified = $modified -replace '\bconst Text\(', 'Text('
        $modified = $modified -replace '\bconst Icon\(', 'Icon('
        $modified = $modified -replace '\bconst BoxDecoration\(', 'BoxDecoration('
        $modified = $modified -replace '\bconst Center\(', 'Center('
        $modified = $modified -replace '\bconst Padding\(', 'Padding('
        $modified = $modified -replace '\bconst SizedBox\(', 'SizedBox('
        $modified = $modified -replace '\bconst Column\(', 'Column('
        $modified = $modified -replace '\bconst Row\(', 'Row('
        $modified = $modified -replace '\bconst Stack\(', 'Stack('
        $modified = $modified -replace '\bconst Wrap\(', 'Wrap('
        $modified = $modified -replace '\bconst Divider\(', 'Divider('
        $modified = $modified -replace '\bconst ListTile\(', 'ListTile('
        $modified = $modified -replace '\bconst Card\(', 'Card('
        $modified = $modified -replace '\bconst Container\(', 'Container('
        $modified = $modified -replace '\bconst Expanded\(', 'Expanded('
        $modified = $modified -replace '\bconst Flexible\(', 'Flexible('
        # Remove const from list literals that contain AppColors
        $modified = $modified -replace 'children: const \[', 'children: ['
        $modified = $modified -replace 'items: const \[', 'items: ['
        $modified = $modified -replace 'tabs: const \[', 'tabs: ['
        $modified = $modified -replace 'actions: const \[', 'actions: ['
        $modified = $modified -replace 'slivers: const \[', 'slivers: ['
    }

    if ($modified -ne $content) {
        Set-Content $_.FullName $modified -NoNewline
        $fixed++
        Write-Host "Fixed: $($_.Name)"
    }
}
Write-Host "Total: $fixed files"
