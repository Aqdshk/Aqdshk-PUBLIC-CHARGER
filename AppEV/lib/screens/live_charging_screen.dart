import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/session_provider.dart';
import '../constants/app_colors.dart';
import 'dart:ui';

class LiveChargingScreen extends StatefulWidget {
  const LiveChargingScreen({super.key});

  @override
  State<LiveChargingScreen> createState() => _LiveChargingScreenState();
}

class _LiveChargingScreenState extends State<LiveChargingScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  SessionProvider? _sessionProvider;

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
    });
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _sessionProvider?.stopPolling();
    super.dispose();
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
          title: const Text('LIVE CHARGING'),
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
                        gradient: const LinearGradient(
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
                      child: const Icon(
                        Icons.bolt_rounded,
                        size: 64,
                        color: AppColors.textTertiary,
                      ),
                    ),
                    const SizedBox(height: 24),
                    Text(
                      'NO ACTIVE SESSION',
                      style: Theme.of(context).textTheme.displayMedium?.copyWith(
                        color: AppColors.primaryGreen,
                        letterSpacing: 2,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Start charging to view live data',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
              );
            }

            final session = sessionProvider.activeSession!;
            final energy = (session['energy'] ?? 0.0).toDouble();
            final power = (session['power'] ?? 0.0).toDouble();
            final voltage = (session['voltage'] ?? 0.0).toDouble();
            final current = (session['current'] ?? 0.0).toDouble();
            final startTime = session['start_time'];
            final duration = session['duration'] ?? '00:00';

            return SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Charger Info Card
                  _FuturisticInfoCard(
                    chargerId: session['charger_id'] ?? 'Unknown Charger',
                    status: 'CHARGING',
                    startTime: startTime ?? 'N/A',
                    duration: duration,
                  ),
                  const SizedBox(height: 32),

                  // Energy Display
                  Center(
                    child: _EnergyDisplay(
                      energy: energy,
                      pulseController: _pulseController,
                    ),
                  ),
                  const SizedBox(height: 32),

                  // Metering Data Grid
                  Text(
                    'METERING DATA',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: AppColors.primaryGreen,
                      letterSpacing: 2,
                    ),
                  ),
                  const SizedBox(height: 16),
                  GridView.count(
                    crossAxisCount: 2,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    crossAxisSpacing: 16,
                    mainAxisSpacing: 16,
                    childAspectRatio: 1.1,
                    children: [
                      _FuturisticMeterCard(
                        label: 'POWER',
                        value: '${(power / 1000).toStringAsFixed(2)}',
                        unit: 'kW',
                        icon: Icons.flash_on_rounded,
                        gradient: [AppColors.primaryGreen, AppColors.mediumGreen],
                      ),
                      _FuturisticMeterCard(
                        label: 'VOLTAGE',
                        value: voltage.toStringAsFixed(1),
                        unit: 'V',
                        icon: Icons.electrical_services_rounded,
                        gradient: [AppColors.primaryGreen, AppColors.darkGreen],
                      ),
                      _FuturisticMeterCard(
                        label: 'CURRENT',
                        value: current.toStringAsFixed(2),
                        unit: 'A',
                        icon: Icons.power_rounded,
                        gradient: const [Color(0xFFFF006E), Color(0xFFC1121F)],
                      ),
                      _FuturisticMeterCard(
                        label: 'COST',
                        value: 'RM ${(energy * 0.50).toStringAsFixed(2)}',
                        unit: '',
                        icon: Icons.attach_money_rounded,
                        gradient: [AppColors.primaryGreen, AppColors.primaryGreen],
                      ),
                    ],
                  ),
                  const SizedBox(height: 32),

                  // Stop Button
                  SizedBox(
                    width: double.infinity,
                    child: Container(
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFFFF006E), Color(0xFFC1121F)],
                        ),
                        borderRadius: BorderRadius.circular(20),
                        boxShadow: [
                          BoxShadow(
                            color: const Color(0xFFFF006E).withOpacity(0.5),
                            blurRadius: 20,
                            spreadRadius: 0,
                          ),
                        ],
                      ),
                      child: ElevatedButton(
                        onPressed: () {
                          _showStopDialog(context, sessionProvider);
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.transparent,
                          shadowColor: Colors.transparent,
                          padding: const EdgeInsets.symmetric(vertical: 18),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(20),
                          ),
                        ),
                        child: const Text(
                          'STOP CHARGING',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 2,
                            color: AppColors.textTertiary,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
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
        title: const Text(
          'STOP CHARGING?',
          style: TextStyle(
            color: AppColors.textTertiary,
            fontWeight: FontWeight.bold,
            letterSpacing: 1.5,
          ),
        ),
        content: const Text(
          'Are you sure you want to stop charging?',
          style: TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text(
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
              child: const Text(
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

class _FuturisticInfoCard extends StatelessWidget {
  final String chargerId;
  final String status;
  final String startTime;
  final String duration;

  const _FuturisticInfoCard({
    required this.chargerId,
    required this.status,
    required this.startTime,
    required this.duration,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface.withOpacity(0.6),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: AppColors.primaryGreen.withOpacity(0.3),
          width: 1,
        ),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [AppColors.primaryGreen, AppColors.mediumGreen],
                        ),
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.primaryGreen.withOpacity(0.5),
                            blurRadius: 10,
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.bolt_rounded,
                        color: AppColors.textTertiary,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            chargerId,
                            style: const TextStyle(
                              color: AppColors.textTertiary,
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.primaryGreen.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(
                                color: AppColors.primaryGreen,
                                width: 1,
                              ),
                            ),
                            child: Text(
                              status,
                              style: const TextStyle(
                                color: AppColors.primaryGreen,
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                                letterSpacing: 1.5,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                _InfoRow('Started', startTime),
                const SizedBox(height: 12),
                _InfoRow('Duration', duration),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textLight,
            fontSize: 14,
          ),
        ),
        Text(
          value,
          style: const TextStyle(
            color: AppColors.textTertiary,
            fontSize: 14,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }
}

class _EnergyDisplay extends StatelessWidget {
  final double energy;
  final AnimationController pulseController;

  const _EnergyDisplay({
    required this.energy,
    required this.pulseController,
  });

  @override
  Widget build(BuildContext context) {
    final progress = (energy / 50.0).clamp(0.0, 1.0); // Assuming 50 kWh max

    return AnimatedBuilder(
      animation: pulseController,
      builder: (context, child) {
        return Container(
          width: 280,
          height: 280,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(
              colors: [
                AppColors.primaryGreen.withOpacity(0.3 * pulseController.value),
                Colors.transparent,
              ],
            ),
          ),
          child: Stack(
            alignment: Alignment.center,
            children: [
              // Outer ring
              SizedBox(
                width: 280,
                height: 280,
                child: CircularProgressIndicator(
                  value: progress,
                  strokeWidth: 8,
                  backgroundColor: AppColors.surface,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    AppColors.primaryGreen,
                  ),
                ),
              ),
              // Inner ring
              SizedBox(
                width: 240,
                height: 240,
                child: CircularProgressIndicator(
                  value: progress,
                  strokeWidth: 6,
                  backgroundColor: AppColors.surface,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    AppColors.primaryGreen,
                  ),
                ),
              ),
              // Center content
              Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    energy.toStringAsFixed(2),
                    style: const TextStyle(
                      color: AppColors.primaryGreen,
                      fontSize: 48,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const Text(
                    'kWh',
                    style: TextStyle(
                      color: AppColors.textLight,
                      fontSize: 18,
                      letterSpacing: 2,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '${(progress * 100).toStringAsFixed(0)}%',
                    style: const TextStyle(
                      color: AppColors.primaryGreen,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}

class _FuturisticMeterCard extends StatelessWidget {
  final String label;
  final String value;
  final String unit;
  final IconData icon;
  final List<Color> gradient;

  const _FuturisticMeterCard({
    required this.label,
    required this.value,
    required this.unit,
    required this.icon,
    required this.gradient,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: gradient.map((c) => c.withOpacity(0.2)).toList(),
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: gradient.first.withOpacity(0.5),
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: gradient.first.withOpacity(0.3),
            blurRadius: 15,
            spreadRadius: 0,
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: LinearGradient(colors: gradient),
                    boxShadow: [
                      BoxShadow(
                        color: gradient.first.withOpacity(0.5),
                        blurRadius: 10,
                      ),
                    ],
                  ),
                  child: Icon(icon, color: Colors.white, size: 24),
                ),
                const SizedBox(height: 16),
                Text(
                  label,
                  style: TextStyle(
                    color: AppColors.textLight,
                    fontSize: 12,
                    letterSpacing: 1.5,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      value,
                      style: TextStyle(
                        color: gradient.first,
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    if (unit.isNotEmpty) ...[
                      const SizedBox(width: 4),
                      Text(
                        unit,
                        style: TextStyle(
                          color: gradient.first.withOpacity(0.7),
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
