import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../constants/app_colors.dart';

class CarbonFootprintScreen extends StatefulWidget {
  const CarbonFootprintScreen({super.key});

  @override
  State<CarbonFootprintScreen> createState() => _CarbonFootprintScreenState();
}

class _CarbonFootprintScreenState extends State<CarbonFootprintScreen> {
  Map<String, dynamic> _data = {};
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final userId = context.read<AuthProvider>().currentUser?.id;
    if (userId == null) {
      setState(() => _loading = false);
      return;
    }
    final data = await ApiService.getCarbonFootprint(userId);
    if (mounted) setState(() { _data = data; _loading = false; });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_ios, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text('Jejak Karbon', // Carbon Footprint
            style: GoogleFonts.inter(color: Colors.white, fontWeight: FontWeight.bold)),
      ),
      body: _loading
          ? Center(child: CircularProgressIndicator(color: Color(0xFF00D4AA)))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  // Hero card
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF00D4AA), Color(0xFF00A080)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Column(
                      children: [
                        Icon(Icons.eco, color: Colors.white, size: 48),
                        SizedBox(height: 12),
                        Text(
                          '${_data['co2_saved_kg'] ?? 0} kg',
                          style: GoogleFonts.inter(
                              color: Colors.white,
                              fontSize: 40,
                              fontWeight: FontWeight.bold),
                        ),
                        Text(
                          'CO₂ Diselamatkan',
                          style: GoogleFonts.inter(color: AppColors.textSecondary, fontSize: 16),
                        ),
                        SizedBox(height: 4),
                        Text(
                          'berbanding kenderaan petrol',
                          style: GoogleFonts.inter(color: AppColors.textTertiary, fontSize: 12),
                        ),
                      ],
                    ),
                  ),

                  SizedBox(height: 16),

                  // Stats grid
                  GridView.count(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    crossAxisCount: 2,
                    childAspectRatio: 1.5,
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 12,
                    children: [
                      _StatCard(
                        icon: Icons.bolt,
                        iconColor: const Color(0xFFFFD700),
                        label: 'Jumlah kWh',
                        value: '${_data['total_kwh'] ?? 0}',
                        unit: 'kWh',
                      ),
                      _StatCard(
                        icon: Icons.local_gas_station,
                        iconColor: const Color(0xFFFF6B6B),
                        label: 'Petrol Jimat',
                        value: '${_data['petrol_saved_l'] ?? 0}',
                        unit: 'liter',
                      ),
                      _StatCard(
                        icon: Icons.park,
                        iconColor: const Color(0xFF00D4AA),
                        label: 'Bersamaan Pokok',
                        value: '${_data['trees_equivalent'] ?? 0}',
                        unit: 'pokok/tahun',
                      ),
                      _StatCard(
                        icon: Icons.history,
                        iconColor: const Color(0xFF6C63FF),
                        label: 'Sesi Cas',
                        value: '${_data['total_sessions'] ?? 0}',
                        unit: 'sesi',
                      ),
                    ],
                  ),

                  SizedBox(height: 16),

                  // This month
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: const Color(0xFF00D4AA).withOpacity(0.2)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Bulan Ini',
                            style: GoogleFonts.inter(
                                color: AppColors.textSecondary, fontSize: 13, fontWeight: FontWeight.w600)),
                        SizedBox(height: 12),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceAround,
                          children: [
                            _MiniStat(
                              label: 'kWh',
                              value: '${_data['this_month_kwh'] ?? 0}',
                              color: const Color(0xFF00D4AA),
                            ),
                            _MiniStat(
                              label: 'CO₂ (kg)',
                              value: '${_data['this_month_co2_kg'] ?? 0}',
                              color: const Color(0xFF00D4AA),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  SizedBox(height: 16),

                  // Fun fact
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1A2E1A),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.green.withOpacity(0.3)),
                    ),
                    child: Row(
                      children: [
                        Text('🌍', style: TextStyle(fontSize: 24)),
                        SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            'Grid elektrik Malaysia menghasilkan 0.585 kg CO₂/kWh. '
                            'Setiap cas EV anda membantu mengurangkan pelepasan karbon!',
                            style: GoogleFonts.inter(color: Colors.green.shade300, fontSize: 12),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String label;
  final String value;
  final String unit;

  const _StatCard({
    required this.icon,
    required this.iconColor,
    required this.label,
    required this.value,
    required this.unit,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: iconColor.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: iconColor, size: 22),
          const Spacer(),
          Text(value,
              style: GoogleFonts.inter(
                  color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
          Text('$unit · $label',
              style: GoogleFonts.inter(color: AppColors.textTertiary, fontSize: 10)),
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _MiniStat({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value,
            style: GoogleFonts.inter(color: color, fontSize: 24, fontWeight: FontWeight.bold)),
        Text(label, style: GoogleFonts.inter(color: AppColors.textTertiary, fontSize: 12)),
      ],
    );
  }
}
