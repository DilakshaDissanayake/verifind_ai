import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Space Grotesk — modern geometric grotesque, crisp at display and body sizes.
/// Tight tracking on display/headline; comfortable leading on body for readability.
class AppTypography {
  AppTypography._();

  static TextTheme textTheme(Color ink) {
    final base = GoogleFonts.spaceGroteskTextTheme();
    final muted = ink.withValues(alpha: 0.52);
    return base
        .copyWith(
          displayLarge: base.displayLarge?.copyWith(
            fontWeight: FontWeight.w700,
            letterSpacing: -1.2,
            height: 1.05,
            color: ink,
          ),
          headlineMedium: base.headlineMedium?.copyWith(
            fontWeight: FontWeight.w700,
            letterSpacing: -0.6,
            height: 1.14,
            color: ink,
          ),
          headlineSmall: base.headlineSmall?.copyWith(
            fontWeight: FontWeight.w700,
            letterSpacing: -0.4,
            height: 1.18,
            color: ink,
          ),
          titleLarge: base.titleLarge?.copyWith(
            fontWeight: FontWeight.w600,
            letterSpacing: -0.2,
            color: ink,
          ),
          titleMedium: base.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            letterSpacing: -0.1,
            color: ink,
          ),
          titleSmall: base.titleSmall?.copyWith(
            fontWeight: FontWeight.w600,
            color: ink,
          ),
          bodyLarge: base.bodyLarge?.copyWith(
            color: ink,
            height: 1.5,
            letterSpacing: 0.1,
          ),
          bodyMedium: base.bodyMedium?.copyWith(
            color: ink,
            height: 1.5,
            letterSpacing: 0.1,
          ),
          bodySmall: base.bodySmall?.copyWith(
            color: muted,
            height: 1.45,
            letterSpacing: 0.1,
          ),
          labelLarge: base.labelLarge?.copyWith(
            fontWeight: FontWeight.w600,
            letterSpacing: 0.2,
          ),
          labelMedium: base.labelMedium?.copyWith(
            fontWeight: FontWeight.w600,
            letterSpacing: 0.1,
          ),
          labelSmall: base.labelSmall?.copyWith(
            fontWeight: FontWeight.w600,
            letterSpacing: 0.3,
          ),
        )
        .apply(fontFamily: GoogleFonts.spaceGrotesk().fontFamily);
  }
}
