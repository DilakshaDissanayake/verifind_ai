import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../design/app_colors.dart';
import '../../design/app_spacing.dart';
import '../../widgets/vf_mark.dart';

/// Branded launch screen — full-bleed white canvas, centered mark, then [onComplete].
class SplashPage extends StatefulWidget {
  const SplashPage({super.key, required this.onComplete});

  final VoidCallback onComplete;

  @override
  State<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends State<SplashPage>
    with SingleTickerProviderStateMixin {
  Timer? _timer;
  late final AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1600),
    )..repeat(reverse: true);

    // Prefer a short branded beat over a long stuck white frame.
    _timer = Timer(const Duration(milliseconds: 2200), () {
      if (mounted) widget.onComplete();
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final bottom = MediaQuery.viewPaddingOf(context).bottom;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.dark.copyWith(
        statusBarColor: Colors.transparent,
        systemNavigationBarColor: Colors.transparent,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: Colors.white,
        body: Stack(
          fit: StackFit.expand,
          children: [
            Positioned(
              top: -80,
              right: -80,
              child: IgnorePointer(
                child: Container(
                  width: 300,
                  height: 300,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        AppColors.brand.withValues(alpha: 0.08),
                        Colors.transparent,
                      ],
                    ),
                  ),
                ),
              ),
            ),
            Positioned(
              bottom: -50,
              left: -50,
              child: IgnorePointer(
                child: Container(
                  width: 220,
                  height: 220,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        AppColors.brandSoft.withValues(alpha: 0.7),
                        Colors.transparent,
                      ],
                    ),
                  ),
                ),
              ),
            ),
            // SizedBox.expand forces full width so Column content stays centered
            // (Stack otherwise left-aligns a shrink-wrapped Column).
            SafeArea(
              child: SizedBox.expand(
                child: Padding(
                  padding: EdgeInsets.only(
                    bottom: bottom > 0 ? 0 : AppSpacing.lg,
                  ),
                  child: Column(
                    children: [
                      const Spacer(flex: 3),
                      AnimatedBuilder(
                        animation: _pulse,
                        builder: (context, child) {
                          final t = _pulse.value;
                          return Stack(
                            alignment: Alignment.center,
                            children: [
                              Opacity(
                                opacity: (0.06 + t * 0.06).clamp(0.0, 0.12),
                                child: Container(
                                  width: 156 + t * 12,
                                  height: 156 + t * 12,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    border: Border.all(
                                      color: AppColors.brand,
                                      width: 1.5,
                                    ),
                                  ),
                                ),
                              ),
                              Opacity(
                                opacity: (0.10 + t * 0.08).clamp(0.0, 0.18),
                                child: Container(
                                  width: 128 + t * 8,
                                  height: 128 + t * 8,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: AppColors.brand.withValues(
                                      alpha: 0.06,
                                    ),
                                    border: Border.all(
                                      color: AppColors.brand,
                                      width: 1.2,
                                    ),
                                  ),
                                ),
                              ),
                              child!,
                            ],
                          );
                        },
                        child:
                            Container(
                                  width: 112,
                                  height: 112,
                                  decoration: BoxDecoration(
                                    color: Colors.white,
                                    borderRadius: BorderRadius.circular(
                                      AppRadius.xl,
                                    ),
                                    border: Border.all(
                                      color: AppColors.lightBorder,
                                    ),
                                    boxShadow: AppShadows.brandGlow(),
                                  ),
                                  padding: const EdgeInsets.all(10),
                                  child: Image.asset(
                                    kVerifindLogoAsset,
                                    fit: BoxFit.contain,
                                  ),
                                )
                                .animate()
                                .scale(
                                  begin: const Offset(0.7, 0.7),
                                  end: const Offset(1, 1),
                                  duration: 520.ms,
                                  curve: Curves.easeOutBack,
                                )
                                .fadeIn(duration: 360.ms),
                      ),
                      const SizedBox(height: AppSpacing.xxl),
                      Text(
                            'VERIFIND',
                            textAlign: TextAlign.center,
                            style: textTheme.headlineMedium?.copyWith(
                              fontWeight: FontWeight.w900,
                              letterSpacing: 4.0,
                              color: AppColors.ink,
                            ),
                          )
                          .animate()
                          .fadeIn(delay: 220.ms, duration: 420.ms)
                          .slideY(
                            begin: 0.2,
                            end: 0,
                            delay: 220.ms,
                            duration: 420.ms,
                            curve: Curves.easeOutCubic,
                          ),
                      const SizedBox(height: AppSpacing.sm),
                      Text(
                        'AI-verified lost & found',
                        textAlign: TextAlign.center,
                        style: textTheme.bodyMedium?.copyWith(
                          color: AppColors.lightInkMuted,
                        ),
                      ).animate().fadeIn(delay: 400.ms, duration: 420.ms),
                      const Spacer(flex: 3),
                      SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.2,
                          color: AppColors.brand.withValues(alpha: 0.75),
                        ),
                      ).animate().fadeIn(delay: 600.ms, duration: 360.ms),
                      const SizedBox(height: AppSpacing.lg),
                      Text(
                        'Powered by AI · Zero Fraud',
                        textAlign: TextAlign.center,
                        style: textTheme.labelSmall?.copyWith(
                          color: AppColors.lightInkMuted.withValues(
                            alpha: 0.55,
                          ),
                          letterSpacing: 0.5,
                        ),
                      ).animate().fadeIn(delay: 750.ms, duration: 400.ms),
                      const SizedBox(height: AppSpacing.xl),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
