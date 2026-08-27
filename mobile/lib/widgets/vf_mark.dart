import 'package:flutter/material.dart';

import '../design/app_colors.dart';
import '../design/app_spacing.dart';

/// Canonical logo asset (shield + magnifying glass mark).
const String kVerifindLogoAsset = 'assets/images/logo.png';

/// VERIFIND wordmark + project logo.
class VfMark extends StatelessWidget {
  const VfMark({
    super.key,
    this.size = 44,
    this.dark = false,
    this.showWordmark = true,
    this.showGlow = false,
  });

  final double size;
  final bool dark;
  final bool showWordmark;

  /// Adds a brand-tinted drop shadow. Use on hero / splash surfaces.
  final bool showGlow;

  @override
  Widget build(BuildContext context) {
    final mark = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: dark ? Colors.white : AppColors.lightSurface,
        borderRadius: BorderRadius.circular(size * 0.28),
        border: Border.all(
          color: dark
              ? Colors.white.withValues(alpha: 0.2)
              : AppColors.lightBorder,
        ),
        boxShadow: showGlow
            ? AppShadows.brandGlow(color: dark ? Colors.black : AppColors.brand)
            : [
                BoxShadow(
                  color: (dark ? Colors.black : AppColors.brand).withValues(
                    alpha: dark ? 0.18 : 0.18,
                  ),
                  blurRadius: size * 0.35,
                  offset: Offset(0, size * 0.1),
                ),
              ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Padding(
        padding: EdgeInsets.all(size * 0.08),
        child: Image.asset(
          kVerifindLogoAsset,
          fit: BoxFit.contain,
          errorBuilder: (_, __, ___) => Icon(
            Icons.shield_outlined,
            color: dark ? AppColors.brand : AppColors.brand,
            size: size * 0.5,
          ),
        ),
      ),
    );

    if (!showWordmark) return mark;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        mark,
        const SizedBox(width: AppSpacing.md),
        Text(
          'VERIFIND',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.w900,
            letterSpacing: 1.4,
            color: dark ? Colors.white : AppColors.ink,
          ),
        ),
      ],
    );
  }
}
