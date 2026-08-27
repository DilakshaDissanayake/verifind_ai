import 'package:flutter/material.dart';

import '../design/app_colors.dart';
import '../design/app_spacing.dart';

enum AppCardTone { surface, ink, mint, peach }

/// Consistent rounded surface. [tone] paints mint / charcoal hero cards
/// without changing tap or layout contracts.
class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.onTap,
    this.padding = const EdgeInsets.all(AppSpacing.lg),
    this.color,
    this.tone = AppCardTone.surface,
  });

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry padding;
  final Color? color;
  final AppCardTone tone;

  @override
  Widget build(BuildContext context) {
    final resolved =
        color ??
        switch (tone) {
          AppCardTone.surface => Colors.white,
          AppCardTone.ink => AppColors.ink,
          AppCardTone.mint => AppColors.brandSoft,
          AppCardTone.peach => AppColors.lost,
        };

    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: tone == AppCardTone.surface
            ? AppShadows.soft()
            : AppShadows.soft(),
      ),
      child: Material(
        color: resolved,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(AppRadius.lg),
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
  }
}

/// Horizontal stat tile used on home / profile (fitness-card language).
class StatGlance extends StatelessWidget {
  const StatGlance({
    super.key,
    required this.label,
    required this.value,
    required this.caption,
    required this.tone,
    this.progress,
    this.icon,
  });

  final String label;
  final String value;
  final String caption;
  final AppCardTone tone;
  final double? progress;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final fg = tone == AppCardTone.ink ? Colors.white : AppColors.ink;
    final muted = fg.withValues(alpha: 0.62);

    return AppCard(
      tone: tone,
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (icon != null) ...[
                Icon(icon, size: 16, color: muted),
                const SizedBox(width: 6),
              ],
              Expanded(
                child: Text(
                  label,
                  style: Theme.of(
                    context,
                  ).textTheme.labelSmall?.copyWith(color: muted),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Text(
                  value,
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: fg,
                    fontWeight: FontWeight.w800,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (progress != null)
                ConfidenceRing(
                  value: progress!,
                  size: 42,
                  color: tone == AppCardTone.ink
                      ? AppColors.brandLight
                      : AppColors.brand,
                  trackColor: fg.withValues(alpha: 0.16),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            caption,
            style: Theme.of(
              context,
            ).textTheme.bodySmall?.copyWith(color: muted),
          ),
        ],
      ),
    );
  }
}

/// Circular progress used on glance cards and match scores.
class ConfidenceRing extends StatelessWidget {
  const ConfidenceRing({
    super.key,
    required this.value,
    this.size = 56,
    this.stroke = 5,
    this.color,
    this.trackColor,
    this.child,
  });

  final double value;
  final double size;
  final double stroke;
  final Color? color;
  final Color? trackColor;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    final clamped = value.clamp(0.0, 1.0);
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _RingPainter(
          value: clamped,
          color: color ?? AppColors.brand,
          track: trackColor ?? AppColors.brand.withValues(alpha: 0.22),
          stroke: stroke,
        ),
        child: child == null ? null : Center(child: child),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter({
    required this.value,
    required this.color,
    required this.track,
    required this.stroke,
  });

  final double value;
  final Color color;
  final Color track;
  final double stroke;

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    final r = (size.width - stroke) / 2;
    final trackPaint = Paint()
      ..color = track
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;
    final fillPaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(c, r, trackPaint);
    canvas.drawArc(
      Rect.fromCircle(center: c, radius: r),
      -1.5708,
      6.2832 * value,
      false,
      fillPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _RingPainter old) =>
      old.value != value || old.color != color || old.track != track;
}
