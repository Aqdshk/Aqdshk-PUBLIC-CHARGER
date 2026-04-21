import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import '../services/api_service.dart';

class RatingReviewScreen extends StatefulWidget {
  final String chargePointId;
  final String chargerName;

  const RatingReviewScreen({
    super.key,
    required this.chargePointId,
    required this.chargerName,
  });

  @override
  State<RatingReviewScreen> createState() => _RatingReviewScreenState();
}

class _RatingReviewScreenState extends State<RatingReviewScreen> {
  List<Map<String, dynamic>> _reviews = [];
  bool _isLoading = true;
  double _avgRating = 0;

  @override
  void initState() {
    super.initState();
    _loadReviews();
  }

  Future<void> _loadReviews() async {
    try {
      final reviews = await ApiService.getChargerReviews(widget.chargePointId);
      final rating = await ApiService.getChargerRating(widget.chargePointId);
      if (mounted) {
        setState(() {
          _reviews = reviews;
          _avgRating = (rating['avg_rating'] as num?)?.toDouble() ?? 0;
          _isLoading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _showWriteReviewDialog() {
    int _selectedStars = 5;
    final _commentController = TextEditingController();
    bool _submitting = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.cardBackground,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return StatefulBuilder(builder: (ctx, setModalState) {
          return Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 24,
              bottom: MediaQuery.of(ctx).viewInsets.bottom + 24,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Write a Review',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  widget.chargerName,
                  style: TextStyle(color: AppColors.textLight, fontSize: 13),
                ),
                SizedBox(height: 20),
                // Star selector
                Center(
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: List.generate(5, (i) {
                      return GestureDetector(
                        onTap: () => setModalState(() => _selectedStars = i + 1),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 6),
                          child: Icon(
                            i < _selectedStars ? Icons.star : Icons.star_border,
                            color: Colors.amber,
                            size: 36,
                          ),
                        ),
                      );
                    }),
                  ),
                ),
                SizedBox(height: 16),
                TextField(
                  controller: _commentController,
                  maxLines: 3,
                  maxLength: 300,
                  style: TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    hintText: 'Share your experience (optional)...',
                    hintStyle: TextStyle(color: AppColors.textLight),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(color: AppColors.borderLight),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(color: AppColors.borderLight),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(color: AppColors.primaryGreen),
                    ),
                    filled: true,
                    fillColor: AppColors.surface,
                    counterStyle: TextStyle(color: AppColors.textLight),
                  ),
                ),
                SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _submitting
                        ? null
                        : () async {
                            setModalState(() => _submitting = true);
                            final ok = await ApiService.submitReview(
                              widget.chargePointId,
                              _selectedStars,
                              _commentController.text.trim().isEmpty
                                  ? null
                                  : _commentController.text.trim(),
                            );
                            if (ctx.mounted) Navigator.pop(ctx);
                            if (ok) {
                              _loadReviews();
                              if (mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text('Review submitted! Thank you.'),
                                    backgroundColor: AppColors.primaryGreen,
                                  ),
                                );
                              }
                            } else {
                              if (mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Failed to submit. Please login first.'),
                                    backgroundColor: Colors.red,
                                  ),
                                );
                              }
                            }
                          },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primaryGreen,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: _submitting
                        ? SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                          )
                        : Text(
                            'SUBMIT REVIEW',
                            style: TextStyle(fontWeight: FontWeight.bold, color: Colors.black),
                          ),
                  ),
                ),
              ],
            ),
          );
        });
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text('Reviews'),
        backgroundColor: AppColors.primaryGreen,
        iconTheme: const IconThemeData(color: Colors.white),
        titleTextStyle: TextStyle(
          color: Colors.white,
          fontSize: 18,
          fontWeight: FontWeight.bold,
        ),
        actions: [
          TextButton.icon(
            onPressed: _showWriteReviewDialog,
            icon: Icon(Icons.rate_review, color: Colors.white, size: 18),
            label: Text('Write', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
      body: _isLoading
          ? Center(child: CircularProgressIndicator(color: AppColors.primaryGreen))
          : Column(
              children: [
                // Rating summary
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: AppColors.cardBackground,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppColors.borderLight),
                  ),
                  child: Row(
                    children: [
                      Column(
                        children: [
                          Text(
                            _avgRating.toStringAsFixed(1),
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 48,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Row(
                            children: List.generate(5, (i) {
                              return Icon(
                                i < _avgRating.round() ? Icons.star : Icons.star_border,
                                color: Colors.amber,
                                size: 18,
                              );
                            }),
                          ),
                          SizedBox(height: 4),
                          Text(
                            '${_reviews.length} review${_reviews.length != 1 ? 's' : ''}',
                            style: TextStyle(color: AppColors.textLight, fontSize: 12),
                          ),
                        ],
                      ),
                      SizedBox(width: 24),
                      Expanded(
                        child: _reviews.isEmpty
                            ? Text(
                                'No reviews yet.\nBe the first to review!',
                                style: TextStyle(color: AppColors.textLight),
                              )
                            : Column(
                                children: List.generate(5, (i) {
                                  final star = 5 - i;
                                  final count = _reviews.where((r) => (r['rating'] as num?)?.toInt() == star).length;
                                  final frac = _reviews.isEmpty ? 0.0 : count / _reviews.length;
                                  return Padding(
                                    padding: const EdgeInsets.symmetric(vertical: 2),
                                    child: Row(
                                      children: [
                                        Text('$star', style: TextStyle(color: AppColors.textLight, fontSize: 11)),
                                        SizedBox(width: 4),
                                        Icon(Icons.star, color: Colors.amber, size: 11),
                                        SizedBox(width: 6),
                                        Expanded(
                                          child: ClipRRect(
                                            borderRadius: BorderRadius.circular(4),
                                            child: LinearProgressIndicator(
                                              value: frac,
                                              backgroundColor: AppColors.surface,
                                              color: Colors.amber,
                                              minHeight: 6,
                                            ),
                                          ),
                                        ),
                                        SizedBox(width: 6),
                                        Text('$count', style: TextStyle(color: AppColors.textLight, fontSize: 11)),
                                      ],
                                    ),
                                  );
                                }),
                              ),
                      ),
                    ],
                  ),
                ),
                // Reviews list
                Expanded(
                  child: _reviews.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.rate_review_outlined, color: AppColors.textLight, size: 64),
                              SizedBox(height: 16),
                              Text(
                                'No reviews yet',
                                style: TextStyle(color: AppColors.textLight, fontSize: 16),
                              ),
                              SizedBox(height: 8),
                              ElevatedButton(
                                onPressed: _showWriteReviewDialog,
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppColors.primaryGreen,
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                                ),
                                child: Text('Write First Review', style: TextStyle(color: Colors.black)),
                              ),
                            ],
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: _reviews.length,
                          itemBuilder: (_, i) {
                            final r = _reviews[i];
                            final rating = (r['rating'] as num?)?.toInt() ?? 0;
                            final comment = r['comment']?.toString() ?? '';
                            final createdAt = r['created_at']?.toString() ?? '';
                            final dateStr = createdAt.length >= 10 ? createdAt.substring(0, 10) : createdAt;
                            return Container(
                              margin: const EdgeInsets.only(bottom: 12),
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: AppColors.cardBackground,
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: AppColors.borderLight),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Row(
                                        children: List.generate(5, (j) => Icon(
                                          j < rating ? Icons.star : Icons.star_border,
                                          color: Colors.amber,
                                          size: 16,
                                        )),
                                      ),
                                      const Spacer(),
                                      Text(
                                        dateStr,
                                        style: TextStyle(color: AppColors.textLight, fontSize: 11),
                                      ),
                                    ],
                                  ),
                                  if (comment.isNotEmpty) ...[
                                    SizedBox(height: 8),
                                    Text(
                                      comment,
                                      style: TextStyle(color: Colors.white, fontSize: 14, height: 1.4),
                                    ),
                                  ],
                                ],
                              ),
                            );
                          },
                        ),
                ),
              ],
            ),
    );
  }
}
