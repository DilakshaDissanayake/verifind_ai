import 'package:flutter/material.dart';

import '../design/app_colors.dart';
import '../design/app_icons.dart';
import '../design/app_spacing.dart';

/// VERIFIND wordmark + geometric shield with gradient identity.
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
        gradient: dark
            ? null
            : const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [AppColors.brand, AppColors.brandDark],
              ),
        color: dark ? Colors.white : null,
        borderRadius: BorderRadius.circular(size * 0.34),
        boxShadow: showGlow
            ? AppShadows.brandGlow(color: dark ? Colors.black : AppColors.brand)
            : [
                BoxShadow(
                  color: (dark ? Colors.black : AppColors.brand).withValues(
                    alpha: dark ? 0.18 : 0.24,
                  ),
                  blurRadius: size * 0.4,
                  offset: Offset(0, size * 0.12),
                ),
              ],
      ),
      alignment: Alignment.center,
      child: Icon(
        AppIcons.shieldCheck,
        color: dark ? AppColors.brand : Colors.white,
        size: size * 0.50,
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
