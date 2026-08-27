import 'package:flutter/material.dart';

import '../design/app_colors.dart';
import '../design/app_spacing.dart';

/// Horizontal confidence/score gauge — scannable mint bar with optional ring.
class ConfidenceMeter extends StatelessWidget {
  const ConfidenceMeter({
    super.key,
    required this.value,
    this.label,
    this.color,
    this.height = 10,
    this.showPercent = true,
  });

  /// 0.0 - 1.0
  final double value;
  final String? label;
  final Color? color;
  final double height;
  final bool showPercent;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    final clamped = value.clamp(0.0, 1.0);
    final barColor = color ??
        (clamped >= 0.75
            ? statusColors.success
            : clamped >= 0.45
                ? statusColors.warning
                : statusColors.danger);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (label != null || showPercent)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.xs),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                if (label != null)
                  Text(label!, style: theme.textTheme.labelMedium),
                if (showPercent)
                  Text(
                    '${(clamped * 100).toStringAsFixed(0)}%',
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: barColor,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
              ],
            ),
          ),
        ClipRRect(
          borderRadius: BorderRadius.circular(AppRadius.pill),
          child: LayoutBuilder(
            builder: (context, constraints) {
              return Stack(
                children: [
                  Container(
                    height: height,
                    width: constraints.maxWidth,
                    color: AppColors.brandSoft,
                  ),
                  TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0, end: clamped),
                    duration: const Duration(milliseconds: 600),
                    curve: Curves.easeOutCubic,
                    builder: (context, animatedValue, _) => Container(
                      height: height,
                      width: constraints.maxWidth * animatedValue,
                      decoration: BoxDecoration(
                        color: barColor,
                        borderRadius: BorderRadius.circular(AppRadius.pill),
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ],
    );
  }
}
