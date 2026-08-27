import 'package:flutter/material.dart';

/// VERIFIND visual language: white surfaces, deep evergreen actions, and mint accents.
/// Green = trust / verification. Orange = lost / attention. Other semantic colors
/// remain distinct so status is never communicated by color alone.
class AppColors {
  AppColors._();

  // Brand — deep evergreen for active states, CTAs, AI features, and progress.
  static const Color brand = Color(0xFF0F6B4F);
  static const Color brandDark = Color(0xFF0A503B);
  static const Color brandLight = Color(0xFF55B98A);
  static const Color brandSoft = Color(0xFFE7F5EE);

  // Deep green-black — dock, hero cards, and high-emphasis text.
  static const Color ink = Color(0xFF10231C);
  static const Color inkSoft = Color(0xFF1B3A2E);

  // Neutrals — light mode (pure white canvas, clean slate tones).
  static const Color lightBg = Color(0xFFF8FCFA);
  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightSurfaceAlt = Color(0xFFF0F7F3);
  static const Color lightBorder = Color(0xFFD9E8DF);
  static const Color lightInk = Color(0xFF10231C);
  static const Color lightInkMuted = Color(0xFF5D7468);

  // Neutrals — dark mode (deep navy-charcoal layers).
  static const Color darkBg = Color(0xFF080D1A);
  static const Color darkSurface = Color(0xFF0F1629);
  static const Color darkSurfaceAlt = Color(0xFF172035);
  static const Color darkBorder = Color(0xFF1E2D45);
  static const Color darkInk = Color(0xFFF1F5F9);         // Slate-100
  static const Color darkInkMuted = Color(0xFF94A3B8);    // Slate-400

  // Semantic — always paired with an icon, never color-only.
  static const Color success = Color(0xFF168F63); // Emerald-600
  static const Color warning = Color(0xFFF59E0B); // Amber-500
  static const Color danger = Color(0xFFF43F5E);  // Rose-500
  static const Color info = Color(0xFF0EA5E9);    // Sky-500

  // Report-type identity.
  static const Color lost = Color(0xFFF97316);    // Orange-500 — urgency, warmth
  static const Color found = Color(0xFF168F63);   // Emerald-600 — trust, resolution
  static const Color lavender = Color(0xFFA78BFA); // Violet-400
}

/// Theme-aware semantic colors not covered by Material's [ColorScheme].
/// Access via `Theme.of(context).extension<AppStatusColors>()!`.
@immutable
class AppStatusColors extends ThemeExtension<AppStatusColors> {
  const AppStatusColors({
    required this.success,
    required this.warning,
    required this.danger,
    required this.info,
    required this.lost,
    required this.found,
    required this.surfaceAlt,
    required this.border,
    required this.shimmerBase,
    required this.shimmerHighlight,
    required this.ink,
    required this.mintSoft,
  });

  final Color success;
  final Color warning;
  final Color danger;
  final Color info;
  final Color lost;
  final Color found;
  final Color surfaceAlt;
  final Color border;
  final Color shimmerBase;
  final Color shimmerHighlight;
  final Color ink;
  final Color mintSoft;

  static const AppStatusColors light = AppStatusColors(
    success: AppColors.success,
    warning: AppColors.warning,
    danger: AppColors.danger,
    info: AppColors.info,
    lost: AppColors.lost,
    found: AppColors.found,
    surfaceAlt: AppColors.lightSurfaceAlt,
    border: AppColors.lightBorder,
    shimmerBase: Color(0xFFDCEBE2),
    shimmerHighlight: Color(0xFFF3FAF6),
    ink: AppColors.ink,
    mintSoft: AppColors.brandSoft,
  );

  static const AppStatusColors dark = AppStatusColors(
    success: Color(0xFF34D399),  // Emerald-400
    warning: Color(0xFFFBBF24),  // Amber-400
    danger: Color(0xFFFB7185),   // Rose-400
    info: Color(0xFF38BDF8),     // Sky-400
    lost: Color(0xFFFB923C),     // Orange-400
    found: Color(0xFF34D399),    // Emerald-400
    surfaceAlt: AppColors.darkSurfaceAlt,
    border: AppColors.darkBorder,
    shimmerBase: Color(0xFF0F1829),
    shimmerHighlight: Color(0xFF172035),
    ink: AppColors.darkInk,
    mintSoft: Color(0xFF13172E),
  );

  /// Confidence-band color for AI match scoring (HIGH / MEDIUM / LOW).
  Color band(String band) {
    switch (band.toUpperCase()) {
      case 'HIGH':
        return success;
      case 'MEDIUM':
        return warning;
      default:
        return info;
    }
  }

  @override
  AppStatusColors copyWith({
    Color? success,
    Color? warning,
    Color? danger,
    Color? info,
    Color? lost,
    Color? found,
    Color? surfaceAlt,
    Color? border,
    Color? shimmerBase,
    Color? shimmerHighlight,
    Color? ink,
    Color? mintSoft,
  }) {
    return AppStatusColors(
      success: success ?? this.success,
      warning: warning ?? this.warning,
      danger: danger ?? this.danger,
      info: info ?? this.info,
      lost: lost ?? this.lost,
      found: found ?? this.found,
      surfaceAlt: surfaceAlt ?? this.surfaceAlt,
      border: border ?? this.border,
      shimmerBase: shimmerBase ?? this.shimmerBase,
      shimmerHighlight: shimmerHighlight ?? this.shimmerHighlight,
      ink: ink ?? this.ink,
      mintSoft: mintSoft ?? this.mintSoft,
    );
  }

  @override
  AppStatusColors lerp(ThemeExtension<AppStatusColors>? other, double t) {
    if (other is! AppStatusColors) return this;
    return AppStatusColors(
      success: Color.lerp(success, other.success, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      danger: Color.lerp(danger, other.danger, t)!,
      info: Color.lerp(info, other.info, t)!,
      lost: Color.lerp(lost, other.lost, t)!,
      found: Color.lerp(found, other.found, t)!,
      surfaceAlt: Color.lerp(surfaceAlt, other.surfaceAlt, t)!,
      border: Color.lerp(border, other.border, t)!,
      shimmerBase: Color.lerp(shimmerBase, other.shimmerBase, t)!,
      shimmerHighlight: Color.lerp(shimmerHighlight, other.shimmerHighlight, t)!,
      ink: Color.lerp(ink, other.ink, t)!,
      mintSoft: Color.lerp(mintSoft, other.mintSoft, t)!,
    );
  }
}
