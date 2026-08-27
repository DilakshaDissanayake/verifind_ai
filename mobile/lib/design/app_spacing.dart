import 'package:flutter/material.dart';

import 'app_colors.dart';

/// Shared spacing / radius / motion / chrome tokens.
class AppSpacing {
  AppSpacing._();

  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double xxl = 32;
  static const double xxxl = 48;

  /// Extra bottom inset so tab content clears the floating dock + FAB.
  /// Dock pill ≈ 64 + side padding; FAB sits just above — keep this tight.
  static const double dockClearance = 96;
}

class AppRadius {
  AppRadius._();

  static const double sm = 12;
  static const double md = 18;
  static const double lg = 24;
  static const double xl = 32;
  static const double xxl = 40;
  static const double pill = 999;
}

class AppMotion {
  AppMotion._();

  static const Duration fast = Duration(milliseconds: 180);
  static const Duration base = Duration(milliseconds: 280);
  static const Duration slow = Duration(milliseconds: 420);
}

class AppShadows {
  AppShadows._();

  static List<BoxShadow> soft({Color? color}) => [
    BoxShadow(
      color: (color ?? const Color(0xFF0F172A)).withValues(alpha: 0.07),
      blurRadius: 20,
      offset: const Offset(0, 6),
    ),
    BoxShadow(
      color: (color ?? const Color(0xFF0F172A)).withValues(alpha: 0.04),
      blurRadius: 6,
      offset: const Offset(0, 2),
    ),
  ];

  static List<BoxShadow> dock() => [
    BoxShadow(
      color: const Color(0xFF0F172A).withValues(alpha: 0.32),
      blurRadius: 32,
      offset: const Offset(0, 14),
    ),
    BoxShadow(
      color: const Color(0xFF0F172A).withValues(alpha: 0.12),
      blurRadius: 8,
      offset: const Offset(0, 4),
    ),
  ];

  static List<BoxShadow> brandGlow({Color? color}) => [
    BoxShadow(
      color: (color ?? AppColors.brand).withValues(alpha: 0.40),
      blurRadius: 28,
      offset: const Offset(0, 10),
      spreadRadius: 2,
    ),
    BoxShadow(
      color: (color ?? AppColors.brand).withValues(alpha: 0.16),
      blurRadius: 8,
      offset: const Offset(0, 3),
    ),
  ];
}
