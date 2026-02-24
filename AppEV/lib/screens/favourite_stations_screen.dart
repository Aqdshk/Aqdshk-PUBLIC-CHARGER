import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import 'charger_detail_screen.dart';

class FavouriteStationsScreen extends StatefulWidget {
  const FavouriteStationsScreen({super.key});

  @override
  State<FavouriteStationsScreen> createState() => _FavouriteStationsScreenState();
}

class _FavouriteStationsScreenState extends State<FavouriteStationsScreen> {
  // Mock favourite stations - In real app, this would come from local storage or API
  List<Map<String, dynamic>> _favourites = [];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'Favourite Stations',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontWeight: FontWeight.bold,
          ),
        ),
        backgroundColor: AppColors.background,
        elevation: 0,
        iconTheme: IconThemeData(color: AppColors.primaryGreen),
      ),
      body: _favourites.isEmpty ? _buildEmptyState() : _buildFavouritesList(),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppColors.primaryGreen.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.bookmark_border_rounded,
                size: 64,
                color: AppColors.primaryGreen,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'No Favourite Stations',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Tap the bookmark icon on any charger to add it to your favourites for quick access.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: AppColors.textLight,
                fontSize: 14,
              ),
            ),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: () {
                Navigator.pop(context);
              },
              icon: const Icon(Icons.search),
              label: const Text('FIND CHARGERS'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primaryGreen,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFavouritesList() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _favourites.length,
      itemBuilder: (context, index) {
        final charger = _favourites[index];
        return _FavouriteStationCard(
          charger: charger,
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => ChargerDetailScreen(charger: charger),
              ),
            );
          },
          onRemove: () {
            setState(() {
              _favourites.removeAt(index);
            });
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: const Text('Removed from favourites'),
                backgroundColor: Colors.orange,
                action: SnackBarAction(
                  label: 'UNDO',
                  textColor: Colors.white,
                  onPressed: () {
                    setState(() {
                      _favourites.insert(index, charger);
                    });
                  },
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _FavouriteStationCard extends StatelessWidget {
  final Map<String, dynamic> charger;
  final VoidCallback onTap;
  final VoidCallback onRemove;

  const _FavouriteStationCard({
    required this.charger,
    required this.onTap,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final name = charger['charge_point_id'] ?? 'Unknown';
    final status = charger['availability'] ?? 'unknown';
    final isAvailable = status == 'available' || status == 'preparing';

    return Dismissible(
      key: Key(name),
      direction: DismissDirection.endToStart,
      background: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: Colors.red,
          borderRadius: BorderRadius.circular(16),
        ),
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      onDismissed: (_) => onRemove(),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.borderLight),
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(16),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.primaryGreen.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      Icons.ev_station,
                      color: AppColors.primaryGreen,
                      size: 28,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          name,
                          style: TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: isAvailable 
                                  ? AppColors.primaryGreen.withOpacity(0.1) 
                                  : Colors.red.withOpacity(0.1),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Text(
                                isAvailable ? 'AVAILABLE' : 'IN USE',
                                style: TextStyle(
                                  color: isAvailable ? AppColors.primaryGreen : Colors.red,
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              '• 1.5 km',
                              style: TextStyle(
                                color: AppColors.textLight,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: Icon(Icons.bookmark, color: AppColors.primaryGreen),
                    onPressed: onRemove,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
