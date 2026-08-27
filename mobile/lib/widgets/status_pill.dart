import 'package:flutter/material.dart';

import '../design/app_colors.dart';
import '../design/app_icons.dart';
import '../design/app_spacing.dart';

/// Small icon+label chip used for report type (LOST/FOUND), match
/// confidence bands (HIGH/MEDIUM/LOW), and report status (active/pending/...).
/// Color is never the only signal — always paired with an icon + text.
class StatusPill extends StatelessWidget {
  const StatusPill({
    super.key,
    required this.label,
    required this.color,
    this.icon,
    this.dense = false,
    this.prominent = false,
  });

  final String label;
  final Color color;
  final IconData? icon;
  final bool dense;

  /// When true, renders a more opaque filled background — use for type badges
  /// (LOST / FOUND) on image overlays where contrast matters.
  final bool prominent;

  factory StatusPill.reportType(BuildContext context, String type) {
    final statusColors = Theme.of(context).extension<AppStatusColors>()!;
    final isLost = type.toUpperCase() == 'LOST';
    return StatusPill(
      label: type.toUpperCase(),
      color: isLost ? statusColors.lost : statusColors.found,
      icon: isLost ? AppIcons.lost : AppIcons.found,
      dense: true,
      prominent: true,
    );
  }

  factory StatusPill.matchBand(BuildContext context, String band) {
    final statusColors = Theme.of(context).extension<AppStatusColors>()!;
    final upper = band.toUpperCase();
    final color = statusColors.band(upper);
    final icon = switch (upper) {
      'HIGH' => AppIcons.checkCircle,
      'MEDIUM' => AppIcons.warningCircle,
      _ => AppIcons.xCircle,
    };
    return StatusPill(
      label: '$upper MATCH',
      color: color,
      icon: icon,
      dense: true,
    );
  }

  factory StatusPill.reportStatus(BuildContext context, String status) {
    final statusColors = Theme.of(context).extension<AppStatusColors>()!;
    final (color, icon) = switch (status.toLowerCase()) {
      'active' => (statusColors.success, AppIcons.checkCircle),
      'matched' => (statusColors.info, AppIcons.link),
      'closed' => (statusColors.info, AppIcons.shieldCheck),
      'processing' => (statusColors.warning, AppIcons.clock),
      'flagged' => (statusColors.danger, AppIcons.warningCircle),
      _ => (statusColors.info, AppIcons.clock),
    };
    return StatusPill(label: status, color: color, icon: icon, dense: true);
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final bgOpacity = prominent ? 0.14 : 0.11;

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: dense ? AppSpacing.sm + 2 : AppSpacing.md,
        vertical: dense ? 4 : AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: bgOpacity),
        borderRadius: BorderRadius.circular(AppRadius.pill),
        border: Border.all(
          color: color.withValues(alpha: prominent ? 0.28 : 0.16),
          width: 1,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: dense ? 11 : 13, color: color),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: (dense ? textTheme.labelSmall : textTheme.labelMedium)
                ?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.3,
                ),
          ),
        ],
      ),
    );
  }
}
