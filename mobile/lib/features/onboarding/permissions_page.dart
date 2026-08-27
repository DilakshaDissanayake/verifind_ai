import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:phosphoricons_flutter/phosphoricons_flutter.dart';

import '../../design/app_colors.dart';
import '../../design/app_spacing.dart';
import '../../widgets/vf_mark.dart';

/// Transparency + consent notice shown before the app requests any OS
/// permission. Explains *why* VERIFIND needs location and media access and
/// how that data is handled, then triggers the native permission prompts.
class PermissionsPage extends StatefulWidget {
  const PermissionsPage({super.key, required this.onDone});

  final VoidCallback onDone;

  @override
  State<PermissionsPage> createState() => _PermissionsPageState();
}

class _PermissionsPageState extends State<PermissionsPage> {
  bool _requesting = false;

  Future<void> _allowAndContinue() async {
    if (_requesting) return;
    setState(() => _requesting = true);
    HapticFeedback.lightImpact();
    try {
      await [
        Permission.locationWhenInUse,
        Permission.camera,
        Permission.photos,
        Permission.microphone,
        Permission.notification,
      ].request();
    } catch (_) {
      // Permission prompts can be denied or unavailable on some platforms;
      // access is re-requested contextually where it is actually needed.
    } finally {
      if (mounted) {
        setState(() => _requesting = false);
        widget.onDone();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final muted = theme.colorScheme.onSurface.withValues(alpha: 0.6);

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.xl,
                  AppSpacing.xxl,
                  AppSpacing.xl,
                  AppSpacing.lg,
                ),
                children: [
                  Container(
                        width: 72,
                        height: 72,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(AppRadius.lg),
                          border: Border.all(color: AppColors.lightBorder),
                        ),
                        padding: const EdgeInsets.all(8),
                        child: Image.asset(
                          kVerifindLogoAsset,
                          fit: BoxFit.contain,
                        ),
                      )
                      .animate()
                      .fadeIn(duration: 360.ms)
                      .scale(
                        begin: const Offset(0.8, 0.8),
                        end: const Offset(1, 1),
                        curve: Curves.easeOutBack,
                      ),
                  const SizedBox(height: AppSpacing.xl),
                  Text(
                    'Your privacy, protected',
                    style: theme.textTheme.headlineMedium,
                  ).animate().fadeIn(delay: 80.ms, duration: 360.ms),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    'VERIFIND only uses these to match lost & found items. '
                    'You are always in control and can change access anytime '
                    'in your device settings.',
                    style: theme.textTheme.bodyMedium?.copyWith(color: muted),
                  ).animate().fadeIn(delay: 120.ms, duration: 360.ms),
                  const SizedBox(height: AppSpacing.xxl),
                  const _PolicyItem(
                    icon: PhosphorIconsFill.mapPin,
                    title: 'Location (GPS)',
                    body:
                        'Used to show items reported near you. Your precise '
                        'position is fuzzed by ~500 m before it ever leaves '
                        'your phone — finders and public maps never see your '
                        'exact spot.',
                    delayMs: 160,
                  ),
                  SizedBox(height: AppSpacing.md),
                  const _PolicyItem(
                    icon: PhosphorIconsBold.camera,
                    title: 'Camera & Photos',
                    body:
                        'Used to attach images to a report. Originals are '
                        'processed securely for verification; only sanitized, '
                        'blurred images are shown in public feeds.',
                    delayMs: 220,
                  ),
                  SizedBox(height: AppSpacing.md),
                  const _PolicyItem(
                    icon: PhosphorIconsBold.bell,
                    title: 'Notifications & voice notes',
                    body:
                        'Notifications keep you updated on likely matches and '
                        'chat messages. Microphone access is used only when '
                        'you record a voice note in a handover chat.',
                    delayMs: 260,
                  ),
                  SizedBox(height: AppSpacing.md),
                  const _PolicyItem(
                    icon: PhosphorIconsBold.lockKey,
                    title: 'How your data is handled',
                    body:
                        'Data is encrypted in transit and used solely to run '
                        'matching and verification. We never sell your data or '
                        'share vault originals.',
                    delayMs: 320,
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.xl,
                AppSpacing.sm,
                AppSpacing.xl,
                AppSpacing.xl,
              ),
              child: Column(
                children: [
                  FilledButton(
                    onPressed: _requesting ? null : _allowAndContinue,
                    child: _requesting
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.4,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Allow access & continue'),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  TextButton(
                    onPressed: _requesting ? null : widget.onDone,
                    child: Text('Maybe later', style: TextStyle(color: muted)),
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

class _PolicyItem extends StatelessWidget {
  const _PolicyItem({
    required this.icon,
    required this.title,
    required this.body,
    required this.delayMs,
  });

  final IconData icon;
  final String title;
  final String body;
  final int delayMs;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
          padding: const EdgeInsets.all(AppSpacing.lg),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(AppRadius.lg),
            boxShadow: AppShadows.soft(),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppColors.brandSoft,
                  borderRadius: BorderRadius.circular(AppRadius.md),
                ),
                alignment: Alignment.center,
                child: Icon(icon, color: AppColors.ink, size: 22),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: theme.textTheme.titleMedium),
                    const SizedBox(height: 2),
                    Text(
                      body,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurface.withValues(
                          alpha: 0.6,
                        ),
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        )
        .animate()
        .fadeIn(delay: delayMs.ms, duration: 360.ms)
        .slideY(begin: 0.15, end: 0, curve: Curves.easeOutCubic);
  }
}
