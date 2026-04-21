import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';
import '../constants/app_colors.dart';

class BookingScreen extends StatefulWidget {
  final Map<String, dynamic> charger;
  const BookingScreen({super.key, required this.charger});

  @override
  State<BookingScreen> createState() => _BookingScreenState();
}

class _BookingScreenState extends State<BookingScreen> {
  DateTime _selectedDate = DateTime.now().add(const Duration(days: 1));
  String? _selectedSlotStart;
  String? _selectedSlotEnd;
  int _durationMin = 60;
  bool _loading = false;
  bool _loadingSlots = false;
  List<dynamic> _slots = [];

  @override
  void initState() {
    super.initState();
    _loadSlots();
  }

  Future<void> _loadSlots() async {
    setState(() => _loadingSlots = true);
    final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate);
    final chargePointId = widget.charger['charge_point_id'] ?? '';
    final slots = await ApiService.getAvailableSlots(chargePointId, dateStr);
    setState(() {
      _slots = slots;
      _loadingSlots = false;
      _selectedSlotStart = null;
      _selectedSlotEnd = null;
    });
  }

  Future<void> _confirmBooking() async {
    if (_selectedSlotStart == null) return;
    setState(() => _loading = true);

    final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate);
    final startTime = '${dateStr}T$_selectedSlotStart:00';
    final chargePointId = widget.charger['charge_point_id'] ?? '';

    final result = await ApiService.createBooking(
      chargePointId,
      startTime: startTime,
      durationMin: _durationMin,
    );

    setState(() => _loading = false);

    if (!mounted) return;
    if (result.containsKey('error')) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(result['error']), backgroundColor: Colors.red),
      );
    } else {
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          backgroundColor: AppColors.cardBackground,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Text('Tempahan Berjaya! ✅',
              style: GoogleFonts.inter(color: Colors.white, fontWeight: FontWeight.bold)),
          content: Text(
            'Tempahan anda untuk ${widget.charger['charge_point_id']} pada '
            '${DateFormat('d MMM yyyy').format(_selectedDate)} jam $_selectedSlotStart '
            'selama $_durationMin minit telah disahkan.',
            style: GoogleFonts.inter(color: AppColors.textSecondary),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(context);
                Navigator.pop(context);
              },
              child: Text('OK', style: GoogleFonts.inter(color: const Color(0xFF00D4AA))),
            ),
          ],
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final chargePointId = widget.charger['charge_point_id'] ?? 'Charger';
    final location = widget.charger['location'] ?? 'Lokasi tidak diketahui';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_ios, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text('Tempah Slot',
            style: GoogleFonts.inter(color: Colors.white, fontWeight: FontWeight.bold)),
      ),
      body: Column(
        children: [
          // Charger info
          Container(
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.cardBackground,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFF00D4AA).withOpacity(0.3)),
            ),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: const Color(0xFF00D4AA).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(Icons.ev_station, color: Color(0xFF00D4AA)),
                ),
                SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(chargePointId,
                          style: GoogleFonts.inter(color: Colors.white, fontWeight: FontWeight.bold)),
                      Text(location,
                          style: GoogleFonts.inter(color: AppColors.textTertiary, fontSize: 12),
                          maxLines: 1, overflow: TextOverflow.ellipsis),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Date selector
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Text('Pilih Tarikh',
                    style: GoogleFonts.inter(color: AppColors.textSecondary, fontSize: 13)),
                const Spacer(),
                GestureDetector(
                  onTap: () async {
                    final picked = await showDatePicker(
                      context: context,
                      initialDate: _selectedDate,
                      firstDate: DateTime.now(),
                      lastDate: DateTime.now().add(const Duration(days: 30)),
                      builder: (ctx, child) => Theme(
                        data: ThemeData.dark().copyWith(
                          colorScheme: const ColorScheme.dark(primary: Color(0xFF00D4AA)),
                        ),
                        child: child!,
                      ),
                    );
                    if (picked != null && picked != _selectedDate) {
                      setState(() => _selectedDate = picked);
                      _loadSlots();
                    }
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: const Color(0xFF00D4AA).withOpacity(0.4)),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.calendar_today, color: Color(0xFF00D4AA), size: 16),
                        SizedBox(width: 6),
                        Text(
                          DateFormat('d MMM yyyy').format(_selectedDate),
                          style: GoogleFonts.inter(color: Colors.white, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),

          SizedBox(height: 16),

          // Duration selector
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Text('Tempoh', style: GoogleFonts.inter(color: AppColors.textSecondary, fontSize: 13)),
                const Spacer(),
                for (final dur in [30, 60, 90, 120])
                  Padding(
                    padding: const EdgeInsets.only(left: 6),
                    child: GestureDetector(
                      onTap: () => setState(() => _durationMin = dur),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: _durationMin == dur
                              ? const Color(0xFF00D4AA)
                              : AppColors.cardBackground,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFF00D4AA).withOpacity(0.4)),
                        ),
                        child: Text(
                          '${dur}m',
                          style: GoogleFonts.inter(
                            color: _durationMin == dur ? Colors.black : AppColors.textSecondary,
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),

          SizedBox(height: 16),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text('Pilih Masa',
                  style: GoogleFonts.inter(color: AppColors.textSecondary, fontSize: 13)),
            ),
          ),
          SizedBox(height: 8),

          // Slots grid
          Expanded(
            child: _loadingSlots
                ? Center(child: CircularProgressIndicator(color: Color(0xFF00D4AA)))
                : _slots.isEmpty
                    ? Center(
                        child: Text('Tiada slot tersedia',
                            style: GoogleFonts.inter(color: AppColors.textTertiary)))
                    : GridView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 4,
                          childAspectRatio: 2.2,
                          crossAxisSpacing: 8,
                          mainAxisSpacing: 8,
                        ),
                        itemCount: _slots.length,
                        itemBuilder: (ctx, i) {
                          final slot = _slots[i];
                          final available = slot['available'] == true;
                          final selected = _selectedSlotStart == slot['start'];
                          return GestureDetector(
                            onTap: available
                                ? () => setState(() {
                                      _selectedSlotStart = slot['start'];
                                      _selectedSlotEnd   = slot['end'];
                                    })
                                : null,
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 150),
                              decoration: BoxDecoration(
                                color: selected
                                    ? const Color(0xFF00D4AA)
                                    : available
                                        ? AppColors.cardBackground
                                        : const Color(0xFF2A1A1A),
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(
                                  color: selected
                                      ? const Color(0xFF00D4AA)
                                      : available
                                          ? const Color(0xFF00D4AA).withOpacity(0.3)
                                          : Colors.red.withOpacity(0.3),
                                ),
                              ),
                              child: Center(
                                child: Text(
                                  slot['start'],
                                  style: GoogleFonts.inter(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w600,
                                    color: selected
                                        ? Colors.black
                                        : available
                                            ? Colors.white
                                            : Colors.red.withOpacity(0.6),
                                  ),
                                ),
                              ),
                            ),
                          );
                        },
                      ),
          ),

          // Confirm button
          Padding(
            padding: const EdgeInsets.all(16),
            child: SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton(
                onPressed: _selectedSlotStart == null || _loading ? null : _confirmBooking,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF00D4AA),
                  disabledBackgroundColor: Colors.grey.shade800,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                child: _loading
                    ? SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, valueColor: AlwaysStoppedAnimation(Colors.black)),
                      )
                    : Text(
                        _selectedSlotStart == null
                            ? 'Pilih masa dahulu'
                            : 'Sahkan Tempahan — $_selectedSlotStart',
                        style: GoogleFonts.inter(
                            color: Colors.black, fontWeight: FontWeight.bold, fontSize: 15),
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
