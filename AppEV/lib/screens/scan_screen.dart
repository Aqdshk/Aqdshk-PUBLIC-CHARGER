import 'dart:math' as math;
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:provider/provider.dart';
import '../constants/app_colors.dart';
import '../providers/charger_provider.dart';
import '../services/api_service.dart';
import 'charger_detail_screen.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen>
    with SingleTickerProviderStateMixin {
  MobileScannerController? _scannerController;
  late AnimationController _animController;
  bool _hasScanned = false;
  bool _isLoading = false;
  bool _torchOn = false;
  bool _cameraPermissionDenied = false;
  bool _cameraError = false;
  final TextEditingController _manualController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    _initScanner();
  }

  void _initScanner() {
    try {
      _scannerController = MobileScannerController(
        detectionSpeed: DetectionSpeed.normal,
        facing: CameraFacing.back,
        torchEnabled: false,
      );
    } catch (e) {
      debugPrint('Scanner init error: $e');
      setState(() {
        _cameraError = true;
      });
    }
  }

  @override
  void dispose() {
    _animController.dispose();
    _scannerController?.dispose();
    _manualController.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_hasScanned || _isLoading) return;

    final barcode = capture.barcodes.firstOrNull;
    if (barcode == null || barcode.rawValue == null) return;

    final code = barcode.rawValue!;
    debugPrint('📱 QR Code scanned: $code');

    setState(() => _hasScanned = true);
    _scannerController?.stop();
    _processScannedCode(code);
  }

  Future<void> _processScannedCode(String code) async {
    setState(() => _isLoading = true);

    // Extract charger ID from QR code
    // QR format could be: "CP001", "plagsini://charger/CP001", or a URL
    String chargerId = _extractChargerId(code);

    try {
      // Look up charger from the charger list
      final chargerProvider =
          Provider.of<ChargerProvider>(context, listen: false);
      Map<String, dynamic>? charger;

      // Search in loaded chargers first
      for (final c in chargerProvider.nearbyChargers) {
        if (c['charge_point_id'] == chargerId) {
          charger = c;
          break;
        }
      }

      // If not found locally, try API
      if (charger == null) {
        charger = await _fetchChargerFromApi(chargerId);
      }

      if (mounted) {
        setState(() => _isLoading = false);
        if (charger != null) {
          _showChargerFound(charger);
        } else {
          _showChargerNotFound(chargerId);
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        _showChargerNotFound(chargerId);
      }
    }
  }

  String _extractChargerId(String code) {
    // Handle various QR code formats
    // URL format: https://plagsini.com/charger/CP001
    // URI format: plagsini://charger/CP001
    // Plain: CP001
    try {
      final uri = Uri.tryParse(code);
      if (uri != null && uri.pathSegments.isNotEmpty) {
        // Get the last path segment as charger ID
        return uri.pathSegments.last;
      }
    } catch (_) {}
    // If it's just a plain string, use it as-is
    return code.trim();
  }

  Future<Map<String, dynamic>?> _fetchChargerFromApi(String chargerId) async {
    try {
      final chargers = await ApiService.getNearbyChargers(0, 0);
      for (final c in chargers) {
        if (c['charge_point_id'] == chargerId) {
          return c;
        }
      }
    } catch (e) {
      debugPrint('Error fetching charger: $e');
    }
    return null;
  }

  void _showChargerFound(Map<String, dynamic> charger) {
    final name = charger['charge_point_id'] ?? 'Unknown';
    final status = charger['availability'] ?? 'unknown';
    final vendor = charger['vendor'] ?? '';
    final model = charger['model'] ?? '';
    final isAvailable = status == 'available' || status == 'preparing';

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          border: Border.all(
            color: AppColors.primaryGreen.withOpacity(0.3),
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Handle
            Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.only(bottom: 20),
              decoration: BoxDecoration(
                color: AppColors.textLight.withOpacity(0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),

            // Success icon
            TweenAnimationBuilder<double>(
              tween: Tween(begin: 0.0, end: 1.0),
              duration: const Duration(milliseconds: 500),
              curve: Curves.elasticOut,
              builder: (context, value, _) => Transform.scale(
                scale: value,
                child: Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppColors.primaryGreen.withOpacity(0.15),
                    boxShadow: [
                      BoxShadow(
                        color: AppColors.primaryGreen.withOpacity(0.3),
                        blurRadius: 20,
                      ),
                    ],
                  ),
                  child: Icon(Icons.ev_station_rounded,
                      color: AppColors.primaryGreen, size: 40),
                ),
              ),
            ),
            const SizedBox(height: 16),

            Text('Charger Found!',
                style: TextStyle(
                    color: AppColors.primaryGreen,
                    fontSize: 22,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(name,
                style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w600)),
            if (vendor.isNotEmpty || model.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('$vendor $model',
                    style: TextStyle(
                        color: AppColors.textLight, fontSize: 13)),
              ),
            const SizedBox(height: 12),

            // Status badge
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              decoration: BoxDecoration(
                color: (isAvailable ? AppColors.primaryGreen : AppColors.error)
                    .withOpacity(0.15),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: isAvailable ? AppColors.primaryGreen : AppColors.error,
                  width: 1,
                ),
              ),
              child: Text(
                isAvailable ? '● Available' : '● ${status.toUpperCase()}',
                style: TextStyle(
                  color: isAvailable ? AppColors.primaryGreen : AppColors.error,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Buttons
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      Navigator.pop(ctx);
                      _resetScanner();
                    },
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.textLight,
                      side: BorderSide(color: AppColors.borderLight),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14)),
                    ),
                    child: const Text('Scan Again'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: ElevatedButton(
                    onPressed: () {
                      Navigator.pop(ctx);
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) =>
                              ChargerDetailScreen(charger: charger),
                        ),
                      ).then((_) => _resetScanner());
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primaryGreen,
                      foregroundColor: AppColors.background,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14)),
                      elevation: 4,
                    ),
                    child: const Text('View Charger',
                        style: TextStyle(
                            fontWeight: FontWeight.bold, fontSize: 15)),
                  ),
                ),
              ],
            ),
            SizedBox(height: MediaQuery.of(ctx).padding.bottom + 8),
          ],
        ),
      ),
    ).whenComplete(() {
      if (mounted && _hasScanned) _resetScanner();
    });
  }

  void _showChargerNotFound(String code) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          border: Border.all(color: AppColors.error.withOpacity(0.3)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.only(bottom: 20),
              decoration: BoxDecoration(
                color: AppColors.textLight.withOpacity(0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Icon(Icons.error_outline, color: AppColors.error, size: 48),
            const SizedBox(height: 12),
            Text('Charger Not Found',
                style: TextStyle(
                    color: AppColors.error,
                    fontSize: 20,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(
              'No charger found for code:\n"$code"',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textLight, fontSize: 14),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.pop(ctx);
                  _resetScanner();
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primaryGreen,
                  foregroundColor: AppColors.background,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
                child: const Text('Try Again',
                    style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ),
            SizedBox(height: MediaQuery.of(ctx).padding.bottom + 8),
          ],
        ),
      ),
    ).whenComplete(() {
      if (mounted && _hasScanned) _resetScanner();
    });
  }

  void _resetScanner() {
    setState(() {
      _hasScanned = false;
      _isLoading = false;
    });
    _scannerController?.start();
  }

  void _showManualEntry() {
    _manualController.clear();
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) => Padding(
        padding:
            EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom),
        child: Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: AppColors.cardBackground,
            borderRadius:
                const BorderRadius.vertical(top: Radius.circular(24)),
            border: Border.all(
                color: AppColors.primaryGreen.withOpacity(0.2)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 20),
                decoration: BoxDecoration(
                  color: AppColors.textLight.withOpacity(0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Text('Enter Charger ID',
                  style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 20,
                      fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Text(
                'Type the charger ID printed on the station',
                style: TextStyle(color: AppColors.textLight, fontSize: 13),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: _manualController,
                autofocus: true,
                textCapitalization: TextCapitalization.characters,
                style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 2),
                decoration: InputDecoration(
                  hintText: 'e.g. CP001',
                  hintStyle: TextStyle(
                      color: AppColors.textLight.withOpacity(0.4),
                      fontSize: 18),
                  filled: true,
                  fillColor: AppColors.surface,
                  prefixIcon: Icon(Icons.ev_station_rounded,
                      color: AppColors.primaryGreen),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                    borderSide: BorderSide.none,
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                    borderSide:
                        BorderSide(color: AppColors.primaryGreen, width: 1.5),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () {
                    final code = _manualController.text.trim();
                    if (code.isNotEmpty) {
                      Navigator.pop(ctx);
                      _processScannedCode(code);
                    }
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primaryGreen,
                    foregroundColor: AppColors.background,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14)),
                  ),
                  child: const Text('Find Charger',
                      style: TextStyle(
                          fontWeight: FontWeight.bold, fontSize: 15)),
                ),
              ),
              SizedBox(height: MediaQuery.of(ctx).padding.bottom + 8),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.background,
            AppColors.surface,
            AppColors.background,
          ],
        ),
      ),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: const Text('SCAN QR CODE'),
          backgroundColor: Colors.transparent,
          actions: [
            // Torch toggle
            if (_scannerController != null && !_cameraError && !_cameraPermissionDenied)
              IconButton(
                icon: Icon(
                  _torchOn ? Icons.flash_on : Icons.flash_off,
                  color: _torchOn ? AppColors.primaryGreen : AppColors.textLight,
                ),
                onPressed: () {
                  _scannerController?.toggleTorch();
                  setState(() => _torchOn = !_torchOn);
                },
              ),
          ],
        ),
        body: Column(
          children: [
            // Camera / Scanner area
            Expanded(
              child: _buildScannerArea(),
            ),

            // Bottom controls (natural size, no forced flex)
            _buildBottomControls(),
          ],
        ),
      ),
    );
  }

  Widget _buildScannerArea() {
    if (_cameraPermissionDenied) {
      return _buildPermissionDenied();
    }
    if (_cameraError) {
      return _buildCameraError();
    }
    if (_scannerController == null) {
      return Center(
        child: CircularProgressIndicator(color: AppColors.primaryGreen),
      );
    }

    return Stack(
      children: [
        // Camera preview
        ClipRRect(
          borderRadius: const BorderRadius.vertical(
              bottom: Radius.circular(24)),
          child: MobileScanner(
            controller: _scannerController!,
            onDetect: _onDetect,
            errorBuilder: (context, error, child) {
              // Handle permission denied
              if (error.errorCode == MobileScannerErrorCode.permissionDenied) {
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (mounted) {
                    setState(() => _cameraPermissionDenied = true);
                  }
                });
                return _buildPermissionDenied();
              }
              return _buildCameraError(
                  message: error.errorDetails?.message);
            },
          ),
        ),

        // Scan overlay
        CustomPaint(
          painter: _ScanOverlayPainter(
            animValue: _animController,
          ),
          size: Size.infinite,
        ),

        // Loading indicator
        if (_isLoading)
          Container(
            color: Colors.black54,
            child: Center(
              child: Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: AppColors.cardBackground,
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.primaryGreen.withOpacity(0.2),
                      blurRadius: 30,
                    ),
                  ],
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    CircularProgressIndicator(
                        color: AppColors.primaryGreen, strokeWidth: 3),
                    const SizedBox(height: 16),
                    Text('Looking up charger...',
                        style: TextStyle(
                            color: AppColors.textPrimary, fontSize: 14)),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildPermissionDenied() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppColors.warning.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.camera_alt_outlined,
                  color: AppColors.warning, size: 48),
            ),
            const SizedBox(height: 24),
            Text('Camera Permission Required',
                style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 20,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Text(
              'To scan QR codes on chargers, please allow camera access in your device settings.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textLight, fontSize: 14),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () {
                // Re-init scanner
                setState(() {
                  _cameraPermissionDenied = false;
                  _cameraError = false;
                });
                _scannerController?.dispose();
                _initScanner();
              },
              icon: const Icon(Icons.refresh),
              label: const Text('Try Again'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primaryGreen,
                foregroundColor: AppColors.background,
                padding:
                    const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'Or use manual entry below',
              style: TextStyle(color: AppColors.textLight, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCameraError({String? message}) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppColors.error.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.videocam_off_rounded,
                  color: AppColors.error, size: 48),
            ),
            const SizedBox(height: 24),
            Text('Camera Not Available',
                style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 20,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Text(
              message ??
                  'Unable to access the camera. You can enter the charger ID manually.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textLight, fontSize: 14),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _showManualEntry,
              icon: const Icon(Icons.keyboard),
              label: const Text('Enter Manually'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primaryGreen,
                foregroundColor: AppColors.background,
                padding:
                    const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBottomControls() {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Instruction text
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.qr_code_scanner_rounded,
                    color: AppColors.primaryGreen, size: 18),
                const SizedBox(width: 6),
                Text(
                  'Point your camera at the QR code',
                  style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 13,
                      fontWeight: FontWeight.w500),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              'Located on the EV charger station',
              style: TextStyle(color: AppColors.textLight, fontSize: 11),
            ),
            const SizedBox(height: 10),

            // Manual entry button
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _showManualEntry,
                icon: Icon(Icons.keyboard_alt_outlined,
                    color: AppColors.primaryGreen, size: 16),
                label: Text('Enter Charger ID Manually',
                    style: TextStyle(
                        color: AppColors.primaryGreen,
                        fontSize: 13,
                        fontWeight: FontWeight.w600)),
                style: OutlinedButton.styleFrom(
                  side: BorderSide(
                      color: AppColors.primaryGreen.withOpacity(0.4)),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ==================== SCAN OVERLAY PAINTER ====================

class _ScanOverlayPainter extends CustomPainter {
  final Animation<double> animValue;

  _ScanOverlayPainter({required this.animValue}) : super(repaint: animValue);

  @override
  void paint(Canvas canvas, Size size) {
    final scanAreaSize = math.min(size.width, size.height) * 0.65;
    final left = (size.width - scanAreaSize) / 2;
    final top = (size.height - scanAreaSize) / 2;
    final scanRect = Rect.fromLTWH(left, top, scanAreaSize, scanAreaSize);

    // Dim overlay outside scan area
    final backgroundPaint = Paint()..color = Colors.black.withOpacity(0.55);
    canvas.drawPath(
      Path.combine(
        PathOperation.difference,
        Path()..addRect(Rect.fromLTWH(0, 0, size.width, size.height)),
        Path()
          ..addRRect(
              RRect.fromRectAndRadius(scanRect, const Radius.circular(16))),
      ),
      backgroundPaint,
    );

    // Corner brackets (neon green)
    final cornerPaint = Paint()
      ..color = const Color(0xFF00FF88)
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    const cornerLength = 30.0;
    const radius = 16.0;

    // Top-left
    canvas.drawPath(
      Path()
        ..moveTo(left, top + cornerLength)
        ..lineTo(left, top + radius)
        ..quadraticBezierTo(left, top, left + radius, top)
        ..lineTo(left + cornerLength, top),
      cornerPaint,
    );

    // Top-right
    canvas.drawPath(
      Path()
        ..moveTo(left + scanAreaSize - cornerLength, top)
        ..lineTo(left + scanAreaSize - radius, top)
        ..quadraticBezierTo(
            left + scanAreaSize, top, left + scanAreaSize, top + radius)
        ..lineTo(left + scanAreaSize, top + cornerLength),
      cornerPaint,
    );

    // Bottom-left
    canvas.drawPath(
      Path()
        ..moveTo(left, top + scanAreaSize - cornerLength)
        ..lineTo(left, top + scanAreaSize - radius)
        ..quadraticBezierTo(
            left, top + scanAreaSize, left + radius, top + scanAreaSize)
        ..lineTo(left + cornerLength, top + scanAreaSize),
      cornerPaint,
    );

    // Bottom-right
    canvas.drawPath(
      Path()
        ..moveTo(left + scanAreaSize - cornerLength, top + scanAreaSize)
        ..lineTo(left + scanAreaSize - radius, top + scanAreaSize)
        ..quadraticBezierTo(left + scanAreaSize, top + scanAreaSize,
            left + scanAreaSize, top + scanAreaSize - radius)
        ..lineTo(left + scanAreaSize, top + scanAreaSize - cornerLength),
      cornerPaint,
    );

    // Animated scan line
    final lineY =
        top + 20 + (scanAreaSize - 40) * animValue.value;
    final scanLinePaint = Paint()
      ..shader = LinearGradient(
        colors: [
          const Color(0xFF00FF88).withOpacity(0),
          const Color(0xFF00FF88).withOpacity(0.8),
          const Color(0xFF00FF88).withOpacity(0),
        ],
      ).createShader(Rect.fromLTWH(left, lineY, scanAreaSize, 2));

    canvas.drawLine(
      Offset(left + 16, lineY),
      Offset(left + scanAreaSize - 16, lineY),
      scanLinePaint..strokeWidth = 2,
    );

    // Glow effect around scan line
    final glowPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          const Color(0xFF00FF88).withOpacity(0),
          const Color(0xFF00FF88).withOpacity(0.08),
          const Color(0xFF00FF88).withOpacity(0),
        ],
      ).createShader(Rect.fromLTWH(left, lineY - 30, scanAreaSize, 60));
    canvas.drawRect(
      Rect.fromLTWH(left + 16, lineY - 30, scanAreaSize - 32, 60),
      glowPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _ScanOverlayPainter oldDelegate) => true;
}
