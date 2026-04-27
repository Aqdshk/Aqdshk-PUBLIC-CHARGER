import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import '../services/api_service.dart';

class ChargingScheduleScreen extends StatefulWidget {
  final String chargerId;
  final String chargerName;

  const ChargingScheduleScreen({
    super.key,
    required this.chargerId,
    required this.chargerName,
  });

  @override
  State<ChargingScheduleScreen> createState() => _ChargingScheduleScreenState();
}

class _ChargingScheduleScreenState extends State<ChargingScheduleScreen> {
  bool _loading = true;
  bool _saving = false;
  int? _scheduleId;

  bool _enabled = true;
  TimeOfDay _startTime = const TimeOfDay(hour: 23, minute: 0);
  TimeOfDay _stopTime = const TimeOfDay(hour: 6, minute: 0);
  // Sun=0, Mon=1, ... Sat=6
  final Set<int> _selectedDays = {0, 1, 2, 3, 4, 5, 6};

  static const List<String> _dayLabels = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
  static const List<String> _dayFullLabels = [
    'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'
  ];

  @override
  void initState() {
    super.initState();
    _loadSchedule();
  }

  Future<void> _loadSchedule() async {
    setState(() => _loading = true);
    try {
      final schedules = await ApiService.getChargingSchedules(widget.chargerId);
      if (!mounted) return;
      if (schedules.isNotEmpty) {
        final s = schedules.first;
        _scheduleId = s['id'] as int?;
        _enabled = s['enabled'] == true;
        _startTime = _parseTime(s['start_time']?.toString() ?? '23:00');
        _stopTime = _parseTime(s['stop_time']?.toString() ?? '06:00');
        final dow = s['days_of_week']?.toString() ?? 'daily';
        _selectedDays.clear();
        if (dow == 'daily') {
          _selectedDays.addAll([0, 1, 2, 3, 4, 5, 6]);
        } else {
          for (final d in dow.split(',')) {
            final n = int.tryParse(d.trim());
            if (n != null) _selectedDays.add(n);
          }
        }
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  TimeOfDay _parseTime(String hhmm) {
    final parts = hhmm.split(':');
    return TimeOfDay(
      hour: int.tryParse(parts[0]) ?? 0,
      minute: int.tryParse(parts.length > 1 ? parts[1] : '0') ?? 0,
    );
  }

  String _formatTime(TimeOfDay t) =>
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

  String _formatTime12(TimeOfDay t) {
    final h = t.hourOfPeriod == 0 ? 12 : t.hourOfPeriod;
    final m = t.minute.toString().padLeft(2, '0');
    final p = t.period == DayPeriod.am ? 'AM' : 'PM';
    return '$h:$m $p';
  }

  Future<void> _pickTime(bool isStart) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: isStart ? _startTime : _stopTime,
      builder: (context, child) => Theme(
        data: Theme.of(context).copyWith(
          colorScheme: ColorScheme.dark(
            primary: AppColors.primaryGreen,
            surface: AppColors.surface,
            onSurface: Colors.white,
          ),
        ),
        child: child!,
      ),
    );
    if (picked != null && mounted) {
      setState(() {
        if (isStart) {
          _startTime = picked;
        } else {
          _stopTime = picked;
        }
      });
    }
  }

  Future<void> _save() async {
    if (_selectedDays.isEmpty) {
      _showSnack('❌ Please select at least one day', AppColors.error);
      return;
    }
    setState(() => _saving = true);
    final dow = _selectedDays.length == 7
        ? 'daily'
        : (_selectedDays.toList()..sort()).join(',');
    final res = await ApiService.saveChargingSchedule(
      widget.chargerId,
      startTime: _formatTime(_startTime),
      stopTime: _formatTime(_stopTime),
      daysOfWeek: dow,
      enabled: _enabled,
    );
    if (!mounted) return;
    setState(() => _saving = false);
    final ok = res['success'] == true;
    _showSnack(
      ok ? '✅ Schedule saved' : '❌ Failed: ${res['message']}',
      ok ? AppColors.success : AppColors.error,
    );
    if (ok) {
      _scheduleId = res['id'] as int? ?? _scheduleId;
    }
  }

  Future<void> _delete() async {
    if (_scheduleId == null) {
      Navigator.pop(context);
      return;
    }
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Delete Schedule?', style: TextStyle(color: Colors.white)),
        content: Text('This schedule will be removed permanently.',
            style: TextStyle(color: AppColors.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text('Cancel', style: TextStyle(color: AppColors.textSecondary)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    setState(() => _saving = true);
    final res = await ApiService.deleteChargingSchedule(widget.chargerId, _scheduleId!);
    if (!mounted) return;
    setState(() => _saving = false);
    if (res['success'] == true) {
      _showSnack('✅ Schedule deleted', AppColors.success);
      Navigator.pop(context);
    } else {
      _showSnack('❌ Failed: ${res['message']}', AppColors.error);
    }
  }

  void _showSnack(String msg, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg, style: const TextStyle(color: Colors.white)),
        backgroundColor: color,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  String _nextRunText() {
    if (!_enabled || _selectedDays.isEmpty) return 'Schedule disabled';
    final now = DateTime.now();
    final today = now.weekday % 7; // Dart Mon=1..Sun=7 → Sun=0..Sat=6
    for (int i = 0; i < 8; i++) {
      final dayIdx = (today + i) % 7;
      if (_selectedDays.contains(dayIdx)) {
        final target = DateTime(now.year, now.month, now.day + i,
            _startTime.hour, _startTime.minute);
        if (target.isAfter(now)) {
          final diff = target.difference(now);
          if (diff.inHours < 24) {
            return 'Next: Today at ${_formatTime12(_startTime)}';
          } else if (diff.inHours < 48) {
            return 'Next: Tomorrow at ${_formatTime12(_startTime)}';
          }
          return 'Next: ${_dayFullLabels[dayIdx]} at ${_formatTime12(_startTime)}';
        }
      }
    }
    return 'No upcoming run';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Schedule Charging',
                style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
            Text(widget.chargerName,
                style: TextStyle(color: AppColors.primaryGreen, fontSize: 12)),
          ],
        ),
        actions: [
          if (_scheduleId != null)
            IconButton(
              icon: Icon(Icons.delete_outline, color: AppColors.error),
              tooltip: 'Delete schedule',
              onPressed: _saving ? null : _delete,
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: AppColors.primaryGreen))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Enable toggle
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppColors.borderLight),
                  ),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: _enabled
                              ? AppColors.primaryGreen.withOpacity(0.15)
                              : AppColors.textSecondary.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(Icons.schedule,
                            color: _enabled ? AppColors.primaryGreen : AppColors.textSecondary,
                            size: 20),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Enable Schedule',
                                style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500)),
                            Text(
                              _enabled ? _nextRunText() : 'Schedule disabled',
                              style: TextStyle(color: AppColors.textSecondary, fontSize: 11),
                            ),
                          ],
                        ),
                      ),
                      Switch(
                        value: _enabled,
                        onChanged: (v) => setState(() => _enabled = v),
                        activeColor: AppColors.primaryGreen,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // Time section
                _sectionHeader(Icons.access_time, 'Time'),
                Container(
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppColors.borderLight),
                  ),
                  child: Column(
                    children: [
                      _timeTile(
                        icon: Icons.play_arrow,
                        iconColor: AppColors.success,
                        label: 'Start charging at',
                        value: _formatTime12(_startTime),
                        onTap: () => _pickTime(true),
                      ),
                      Divider(height: 1, color: AppColors.borderLight, indent: 54),
                      _timeTile(
                        icon: Icons.stop,
                        iconColor: AppColors.error,
                        label: 'Stop charging at',
                        value: _formatTime12(_stopTime),
                        onTap: () => _pickTime(false),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // Days section
                _sectionHeader(Icons.date_range, 'Repeat on'),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppColors.borderLight),
                  ),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: List.generate(7, (i) {
                          final selected = _selectedDays.contains(i);
                          return GestureDetector(
                            onTap: () => setState(() {
                              if (selected) {
                                _selectedDays.remove(i);
                              } else {
                                _selectedDays.add(i);
                              }
                            }),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 150),
                              width: 36,
                              height: 36,
                              decoration: BoxDecoration(
                                color: selected ? AppColors.primaryGreen : Colors.transparent,
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: selected ? AppColors.primaryGreen : AppColors.borderLight,
                                  width: 1.5,
                                ),
                              ),
                              child: Center(
                                child: Text(
                                  _dayLabels[i],
                                  style: TextStyle(
                                    color: selected ? Colors.black : AppColors.textSecondary,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                            ),
                          );
                        }),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          _presetChip('Daily', () => setState(() {
                                _selectedDays..clear()..addAll([0,1,2,3,4,5,6]);
                              })),
                          const SizedBox(width: 8),
                          _presetChip('Weekdays', () => setState(() {
                                _selectedDays..clear()..addAll([1,2,3,4,5]);
                              })),
                          const SizedBox(width: 8),
                          _presetChip('Weekends', () => setState(() {
                                _selectedDays..clear()..addAll([0,6]);
                              })),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),

                // Save button
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primaryGreen,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    onPressed: _saving ? null : _save,
                    icon: _saving
                        ? const SizedBox(
                            width: 18, height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                        : const Icon(Icons.save, color: Colors.black),
                    label: Text(
                      _scheduleId == null ? 'Save Schedule' : 'Update Schedule',
                      style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 15),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppColors.cardBackground,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.borderLight),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.info_outline, color: AppColors.textSecondary, size: 18),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Charging will start/stop automatically at the set times. Charger must be online and plugged in.',
                          style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
    );
  }

  Widget _sectionHeader(IconData icon, String title) => Padding(
        padding: const EdgeInsets.only(left: 4, bottom: 10),
        child: Row(
          children: [
            Icon(icon, color: AppColors.primaryGreen, size: 16),
            const SizedBox(width: 6),
            Text(title,
                style: TextStyle(
                    color: AppColors.primaryGreen,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.5)),
          ],
        ),
      );

  Widget _timeTile({
    required IconData icon,
    required Color iconColor,
    required String label,
    required String value,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: iconColor.withOpacity(0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, color: iconColor, size: 20),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Text(label,
                  style: const TextStyle(color: Colors.white, fontSize: 14)),
            ),
            Text(value,
                style: TextStyle(
                    color: AppColors.primaryGreen,
                    fontSize: 16,
                    fontWeight: FontWeight.bold)),
            const SizedBox(width: 6),
            Icon(Icons.chevron_right, color: AppColors.textSecondary, size: 18),
          ],
        ),
      ),
    );
  }

  Widget _presetChip(String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.borderLight),
        ),
        child: Text(label,
            style: TextStyle(
                color: AppColors.textSecondary,
                fontSize: 11,
                fontWeight: FontWeight.w600)),
      ),
    );
  }
}
