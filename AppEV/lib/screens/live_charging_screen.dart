import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../providers/session_provider.dart';
import '../constants/app_colors.dart';
import '../widgets/charging_battery_car.dart';
import 'dart:ui';
import '../providers/theme_provider.dart';

class LiveChargingScreen extends StatefulWidget {
  const LiveChargingScreen({super.key});

  @override
  State<LiveChargingScreen> createState() => _LiveChargingScreenState();
}

class _LiveChargingScreenState extends State<LiveChargingScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  SessionProvider? _sessionProvider;

  // Power history for kW chart (x = seconds elapsed, y = kW)
  final List<FlSpot> _powerHistory = [];
  double _chartTime = 0;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _sessionProvider = Provider.of<SessionProvider>(context, listen: false);
      _sessionProvider?.startPolling();
      _sessionProvider?.addListener(_onSessionUpdate);
    });
  }

  /// Clock time from the API's start_time, which is Malaysian wall time with
  /// no offset. Only the time of day is useful on a live screen; the date is
  /// today by definition.
  String _clockOf(String? iso) {
    if (iso == null || iso.isEmpty) return '--:--';
    try {
      final norm = (iso.contains('+') || iso.endsWith('Z')) ? iso : '$iso+08:00';
      final t = DateTime.parse(norm).toLocal();
      return '${t.hour.toString().padLeft(2, '0')}:'
          '${t.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return '--:--';
    }
  }

  double _parseNum(dynamic v) {
    if (v == null) return 0.0;
    if (v is num) return v.toDouble();
    if (v is String) return double.tryParse(v) ?? 0.0;
    return 0.0;
  }

  void _onSessionUpdate() {
    try {
      final session = _sessionProvider?.activeSession;
      if (session == null) return;
      final raw = _parseNum(session['power']);
      final power = raw; // already in kW from the metering endpoint
      if (!power.isFinite) return;
      if (!mounted) return;
      setState(() {
        _chartTime += 10; // each poll ≈ 10s
        _powerHistory.add(FlSpot(_chartTime, power));
        // Keep only last 30 data points
        if (_powerHistory.length > 30) _powerHistory.removeAt(0);
      });
    } catch (e, st) {
      // Never let listener exceptions propagate — they'd flood the console.
      debugPrint('_onSessionUpdate error: $e\n$st');
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _sessionProvider?.removeListener(_onSessionUpdate);
    _sessionProvider?.stopPolling();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Rebuild when the palette swaps: AppColors is global, so
    // nothing else would tell this widget its colours changed.
    context.watch<ThemeProvider>();
    return Container(
      decoration: BoxDecoration(
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
          title: Text('LIVE CHARGING'),
          backgroundColor: Colors.transparent,
        ),
        body: Consumer<SessionProvider>(
          builder: (context, sessionProvider, _) {
            if (sessionProvider.activeSession == null) {
              return Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(32),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: LinearGradient(
                          colors: [AppColors.primaryGreen, AppColors.primaryGreen],
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.primaryGreen.withOpacity(0.5),
                            blurRadius: 30,
                            spreadRadius: 5,
                          ),
                        ],
                      ),
                      child: Icon(
                        Icons.bolt_rounded,
                        size: 64,
                        color: AppColors.textTertiary,
                      ),
                    ),
                    SizedBox(height: 24),
                    Text(
                      'NO ACTIVE SESSION',
                      style: Theme.of(context).textTheme.displayMedium?.copyWith(
                        color: AppColors.primaryGreen,
                        letterSpacing: 2,
                      ),
                    ),
                    SizedBox(height: 8),
                    Text(
                      'Start charging to view live data',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
              );
            }

            final session = sessionProvider.activeSession!;
            // Defensive parsing — API may return numbers as num OR String
            double _num(dynamic v) {
              double r = 0.0;
              if (v == null) return 0.0;
              if (v is num) {
                r = v.toDouble();
              } else if (v is String) {
                r = double.tryParse(v) ?? 0.0;
              }
              return r.isFinite ? r : 0.0;
            }
            final energy = _num(session['energy']);
            final power = _num(session['power']);
            final voltage = _num(session['voltage']);
            final current = _num(session['current']);
            final startTime = session['start_time']?.toString();
            final duration = (session['duration'] ?? '00:00').toString();
            // Null, not zero, when the charger never reported it. Showing 0%
            // would tell the driver the battery is flat.
            final rawSoc = session['soc'];
            final soc = rawSoc == null ? null : _num(rawSoc);
            // Energy still flowing, as opposed to a session that has been
            // stopped but not yet closed. Keeps the animation honest.
            final isCharging = power > 0.05 || current > 0.2;
            // The API prices the session against the charger's own tariff.
            // Falling back to a flat rate would quote the wrong figure on any
            // charger not priced at 50 sen.
            final cost = session['cost'] != null
                ? _num(session['cost'])
                : energy * _num(session['tariff_per_kwh'] ?? 0.50);

            // One screen, no scrolling on a normal phone. The car takes
            // whatever height is left after the fixed rows, so the panel
            // adapts to the device instead of assuming one size.
            return LayoutBuilder(
              builder: (context, box) {
                final showGraph = box.maxHeight > 660;
                return Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _SessionHeader(
                        chargerId: (session['charge_point_id'] ??
                                    session['charger_id'])
                                ?.toString() ??
                            'Unknown',
                        duration: duration,
                        charging: isCharging,
                      ),
                      const SizedBox(height: 4),

                      // The battery is what the driver is actually waiting on,
                      // so it gets the room that is left.
                      Expanded(
                        child: Center(
                          child: ChargingBatteryCar(
                            soc: soc,
                            isCharging: isCharging,
                            energyKwh: energy,
                          ),
                        ),
                      ),

                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: _Stat(
                              label: 'ENERGY',
                              value: energy.toStringAsFixed(2),
                              unit: 'kWh',
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: _Stat(
                              label: 'POWER',
                              value: power.toStringAsFixed(1),
                              unit: 'kW',
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: _Stat(
                              label: 'COST',
                              value: 'RM ${cost.toStringAsFixed(2)}',
                              unit: '',
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: _Stat(
                              label: 'VOLTAGE',
                              value: voltage.toStringAsFixed(0),
                              unit: 'V',
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: _Stat(
                              label: 'CURRENT',
                              value: current.toStringAsFixed(1),
                              unit: 'A',
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: _Stat(
                              label: 'STARTED',
                              value: _clockOf(startTime),
                              unit: '',
                            ),
                          ),
                        ],
                      ),

                      // Dropped rather than squeezed on a short screen: a
                      // 40px graph tells nobody anything.
                      if (showGraph) ...[
                        const SizedBox(height: 10),
                        SizedBox(
                          height: 92,
                          child: _PowerChart(spots: _powerHistory),
                        ),
                      ],

                      const SizedBox(height: 12),
                      SizedBox(
                        height: 52,
                        child: ElevatedButton(
                          onPressed: () =>
                              _showStopDialog(context, sessionProvider),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF2A1218),
                            foregroundColor: const Color(0xFFFF5C7A),
                            elevation: 0,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14),
                              side: const BorderSide(color: Color(0xFF5A2030)),
                            ),
                          ),
                          child: const Text(
                            'STOP CHARGING',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              letterSpacing: 1.5,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }

  void _showStopDialog(BuildContext context, SessionProvider sessionProvider) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(
            color: const Color(0xFFFF006E).withOpacity(0.5),
            width: 1,
          ),
        ),
        title: Text(
          'STOP CHARGING?',
          style: TextStyle(
            color: AppColors.textTertiary,
            fontWeight: FontWeight.bold,
            letterSpacing: 1.5,
          ),
        ),
        content: Text(
          'Are you sure you want to stop charging?',
          style: TextStyle(color: AppColors.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(
              'CANCEL',
              style: TextStyle(color: AppColors.primaryGreen),
            ),
          ),
          Container(
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFFFF006E), Color(0xFFC1121F)],
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: ElevatedButton(
              onPressed: () async {
                await sessionProvider.stopCharging();
                if (context.mounted) {
                  Navigator.pop(context);
                  Navigator.pop(context);
                }
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.transparent,
                shadowColor: Colors.transparent,
              ),
              child: Text(
                'STOP',
                style: TextStyle(
                  color: AppColors.textTertiary,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Charger identity, state and elapsed time on one line, so the panel spends
/// its height on the battery rather than on a card.
class _SessionHeader extends StatelessWidget {
  const _SessionHeader({
    required this.chargerId,
    required this.duration,
    required this.charging,
  });

  final String chargerId;
  final String duration;
  final bool charging;

  @override
  Widget build(BuildContext context) {
    // Rebuild when the palette swaps: AppColors is global, so
    // nothing else would tell this widget its colours changed.
    context.watch<ThemeProvider>();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.primaryGreen.withOpacity(0.18)),
      ),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: charging ? AppColors.primaryGreen : AppColors.warning,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  chargerId,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                Text(
                  charging ? 'Charging' : 'Connected',
                  style: TextStyle(
                    fontSize: 11,
                    color: AppColors.textTertiary.withOpacity(0.75),
                  ),
                ),
              ],
            ),
          ),
          Text(
            duration,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w500,
              color: AppColors.primaryGreen,
              fontFeatures: [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}

/// One compact reading. Deliberately quiet: six of these sit together, and
/// six saturated tiles fight each other and the battery for attention.
class _Stat extends StatelessWidget {
  const _Stat({required this.label, required this.value, required this.unit});

  final String label;
  final String value;
  final String unit;

  @override
  Widget build(BuildContext context) {
    // Rebuild when the palette swaps: AppColors is global, so
    // nothing else would tell this widget its colours changed.
    context.watch<ThemeProvider>();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 9),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.borderLight.withOpacity(0.7)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 9,
              letterSpacing: 1.2,
              color: AppColors.textTertiary.withOpacity(0.65),
            ),
          ),
          const SizedBox(height: 3),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  value,
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                    fontFeatures: [FontFeature.tabularFigures()],
                  ),
                ),
                if (unit.isNotEmpty) ...[
                  const SizedBox(width: 3),
                  Text(
                    unit,
                    style: TextStyle(
                      fontSize: 10,
                      color: AppColors.textTertiary.withOpacity(0.8),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}


class _PowerChart extends StatelessWidget {
  final List<FlSpot> spots;

  const _PowerChart({required this.spots});

  @override
  Widget build(BuildContext context) {
    // Rebuild when the palette swaps: AppColors is global, so
    // nothing else would tell this widget its colours changed.
    context.watch<ThemeProvider>();
    // fl_chart needs ≥2 spots when isCurved=true; single-point curve crashes in release.
    // Also guard against NaN/Infinity in y values that would break maxY calculation.
    final safeSpots = spots.where((s) => s.y.isFinite).toList();
    final displaySpots = safeSpots.length < 2
        ? const [FlSpot(0, 0), FlSpot(1, 0)]
        : safeSpots;
    final maxY = safeSpots.isEmpty
        ? 10.0
        : (safeSpots.map((s) => s.y).reduce((a, b) => a > b ? a : b) * 1.2)
            .clamp(1.0, 1000000.0);

    return Container(
      height: 180,
      padding: const EdgeInsets.fromLTRB(8, 16, 16, 8),
      decoration: BoxDecoration(
        color: AppColors.surface.withOpacity(0.6),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.primaryGreen.withOpacity(0.3)),
      ),
      child: LineChart(
        LineChartData(
          minY: 0,
          maxY: maxY,
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            horizontalInterval: maxY / 4,
            getDrawingHorizontalLine: (v) => FlLine(
              color: AppColors.primaryGreen.withOpacity(0.1),
              strokeWidth: 1,
            ),
          ),
          borderData: FlBorderData(show: false),
          titlesData: FlTitlesData(
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 36,
                getTitlesWidget: (v, _) => Text(
                  v.toStringAsFixed(1),
                  style: TextStyle(color: AppColors.textLight, fontSize: 10),
                ),
              ),
            ),
            rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            bottomTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          ),
          lineBarsData: [
            LineChartBarData(
              spots: displaySpots,
              isCurved: true,
              curveSmoothness: 0.35,
              color: AppColors.primaryGreen,
              barWidth: 2.5,
              dotData: const FlDotData(show: false),
              belowBarData: BarAreaData(
                show: true,
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    AppColors.primaryGreen.withOpacity(0.25),
                    AppColors.primaryGreen.withOpacity(0.0),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
