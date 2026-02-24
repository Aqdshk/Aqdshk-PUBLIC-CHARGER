import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../providers/session_provider.dart';
import '../constants/app_colors.dart';

class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Charging History'),
        backgroundColor: Colors.transparent,
      ),
      body: Consumer<SessionProvider>(
        builder: (context, sessionProvider, _) {
          if (sessionProvider.isLoading) {
            return const Center(child: CircularProgressIndicator(color: AppColors.primaryGreen));
          }

          if (sessionProvider.history.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.history, size: 64, color: AppColors.textLight),
                  const SizedBox(height: 16),
                  Text('No charging history', style: TextStyle(fontSize: 18, color: AppColors.textLight)),
                ],
              ),
            );
          }

          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: sessionProvider.history.length,
            itemBuilder: (context, index) {
              final session = sessionProvider.history[index];
              return Container(
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: AppColors.cardBackground,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppColors.borderLight),
                ),
                child: Theme(
                  data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                  child: ExpansionTile(
                    leading: CircleAvatar(
                      backgroundColor: session['status'] == 'completed'
                          ? AppColors.primaryGreen
                          : Colors.orange,
                      child: const Icon(Icons.bolt, color: Colors.white),
                    ),
                    title: Text(session['charger_id'] ?? 'Unknown Charger', style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w600)),
                    subtitle: Text(
                      DateFormat('MMM dd, yyyy • HH:mm').format(
                        DateTime.parse(session['start_time'] ?? DateTime.now().toString()),
                      ),
                      style: TextStyle(color: AppColors.textLight, fontSize: 12),
                    ),
                    trailing: Text(
                      'RM ${session['cost']?.toStringAsFixed(2) ?? '0.00'}',
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppColors.primaryGreen),
                    ),
                    children: [
                      Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          children: [
                            _HistoryRow('Status', session['status'] ?? 'Unknown'),
                            _HistoryRow('Energy', '${session['energy']?.toStringAsFixed(2) ?? '0.00'} kWh'),
                            _HistoryRow('Duration', session['duration'] ?? '00:00'),
                            _HistoryRow('Start Time', DateFormat('MMM dd, yyyy HH:mm').format(
                              DateTime.parse(session['start_time'] ?? DateTime.now().toString()),
                            )),
                            if (session['stop_time'] != null)
                              _HistoryRow('Stop Time', DateFormat('MMM dd, yyyy HH:mm').format(
                                DateTime.parse(session['stop_time']),
                              )),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class _HistoryRow extends StatelessWidget {
  final String label;
  final String value;

  const _HistoryRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: AppColors.textLight)),
          Text(value, style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary)),
        ],
      ),
    );
  }
}
