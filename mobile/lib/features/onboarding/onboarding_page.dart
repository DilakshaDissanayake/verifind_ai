import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:phosphoricons_flutter/phosphoricons_flutter.dart';

import '../../design/app_colors.dart';
import '../../design/app_spacing.dart';

class _Slide {
  const _Slide({
    required this.icon,
    required this.title,
    required this.body,
    required this.tone,
  });

  final IconData icon;
  final String title;
  final String body;
  final Color tone;
}

const _slides = <_Slide>[
  _Slide(
    icon: PhosphorIconsBold.cameraPlus,
    title: 'Report in seconds',
    body:
        'Snap a photo of anything you lost or found. Our AI reads the '
        'details and does the tedious cataloguing for you.',
    tone: AppColors.brand,
  ),
  _Slide(
    icon: PhosphorIconsBold.arrowsLeftRight,
    title: 'Smart AI matching',
    body:
        'A dual vision + text engine compares reports and surfaces the most '
        'likely matches with a confidence score — like the 96% you saw.',
    tone: AppColors.success,
  ),
  _Slide(
    icon: PhosphorIconsFill.shieldCheck,
    title: 'Verified & private',
    body:
        'Ownership is proven through secure verification. Your exact '
        'location and original photos are never exposed publicly.',
    tone: AppColors.brandDark,
  ),
];

/// Swipeable value-proposition intro shown once on first launch.
class OnboardingPage extends StatefulWidget {
  const OnboardingPage({super.key, required this.onDone});

  final VoidCallback onDone;

  @override
  State<OnboardingPage> createState() => _OnboardingPageState();
}

class _OnboardingPageState extends State<OnboardingPage> {
  final _controller = PageController();
  int _index = 0;

  bool get _isLast => _index == _slides.length - 1;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _next() {
    HapticFeedback.selectionClick();
    if (_isLast) {
      widget.onDone();
      return;
    }
    _controller.nextPage(duration: AppMotion.base, curve: Curves.easeOutCubic);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final slide = _slides[_index];

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: Padding(
                padding: const EdgeInsets.only(
                  top: AppSpacing.sm,
                  right: AppSpacing.sm,
                ),
                child: TextButton(
                  onPressed: widget.onDone,
                  child: const Text('Skip'),
                ),
              ),
            ),
            Expanded(
              child: PageView.builder(
                controller: _controller,
                itemCount: _slides.length,
                onPageChanged: (i) => setState(() => _index = i),
                itemBuilder: (context, i) {
                  final s = _slides[i];
                  return Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.xl,
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Container(
                              width: 168,
                              height: 168,
                              decoration: BoxDecoration(
                                color: s.tone,
                                borderRadius: BorderRadius.circular(
                                  AppRadius.xxl,
                                ),
                              ),
                              alignment: Alignment.center,
                              child: Icon(
                                s.icon,
                                size: 72,
                                color:
                                    s.tone == AppColors.success ||
                                        s.tone == AppColors.brandDark
                                    ? Colors.white
                                    : AppColors.ink,
                              ),
                            )
                            .animate(key: ValueKey('icon$i'))
                            .scale(
                              begin: const Offset(0.82, 0.82),
                              end: const Offset(1, 1),
                              duration: 380.ms,
                              curve: Curves.easeOutBack,
                            )
                            .fadeIn(duration: 320.ms),
                        const SizedBox(height: AppSpacing.xxl),
                        Text(
                              s.title,
                              textAlign: TextAlign.center,
                              style: theme.textTheme.headlineMedium,
                            )
                            .animate(key: ValueKey('title$i'))
                            .fadeIn(duration: 360.ms),
                        const SizedBox(height: AppSpacing.md),
                        Text(
                              s.body,
                              textAlign: TextAlign.center,
                              style: theme.textTheme.bodyLarge?.copyWith(
                                color: theme.colorScheme.onSurface.withValues(
                                  alpha: 0.55,
                                ),
                              ),
                            )
                            .animate(key: ValueKey('body$i'))
                            .fadeIn(delay: 80.ms, duration: 360.ms),
                      ],
                    ),
                  );
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(_slides.length, (i) {
                      final active = i == _index;
                      return AnimatedContainer(
                        duration: AppMotion.fast,
                        margin: const EdgeInsets.symmetric(horizontal: 4),
                        width: active ? 22 : 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: active ? AppColors.ink : slide.tone,
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                        ),
                      );
                    }),
                  ),
                  const SizedBox(height: AppSpacing.xl),
                  FilledButton(
                    onPressed: _next,
                    child: Text(_isLast ? 'Get started' : 'Next'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
