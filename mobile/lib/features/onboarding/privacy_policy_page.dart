import 'package:flutter/material.dart';

import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';
import '../../widgets/vf_mark.dart';

/// Short academic privacy notice shown to all users.
class PrivacyPolicyPage extends StatelessWidget {
  const PrivacyPolicyPage({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final muted = theme.colorScheme.onSurface.withValues(alpha: 0.65);

    return Scaffold(
      appBar: AppBar(title: const Text('Privacy & safety')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.xl,
          AppSpacing.lg,
          AppSpacing.xl,
          AppSpacing.xxxl,
        ),
        children: [
          const VfMark(size: 40),
          const SizedBox(height: AppSpacing.lg),
          Text('Privacy policy (summary)', style: theme.textTheme.headlineSmall),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'VERIFIND is an academic lost-and-found MVP. We collect only what '
            'is needed to match items, verify ownership, and keep users safe.',
            style: theme.textTheme.bodyMedium?.copyWith(color: muted),
          ),
          const SizedBox(height: AppSpacing.xl),
          const _Section(
            icon: AppIcons.shieldCheck,
            title: 'What we store',
            body:
                'Account email, optional display name, emergency contact number, '
                'report text/photos, approximate GPS (fuzzed ~500 m), chat messages '
                'for matched handovers, and admin audit events for moderation.',
          ),
          const _Section(
            icon: AppIcons.eyeSlash,
            title: 'What the public sees',
            body:
                'Public feeds show sanitized images only (unique marks blurred). '
                'Vault originals and hidden features are never exposed on public APIs. '
                'Exact GPS is not published.',
          ),
          const _Section(
            icon: AppIcons.phone,
            title: 'Emergency contact',
            body:
                'Your emergency contact is private. Admins may reveal it only when '
                'investigating a safety or fraud issue, and that access is audited. '
                'It is not shown to other users in the app.',
          ),
          const _Section(
            icon: AppIcons.lock,
            title: 'Your control',
            body:
                'You can change your password from Profile. You can deny device '
                'permissions in system settings. Contact an administrator if you '
                'need your account reviewed or closed for this academic deployment.',
          ),
          const SizedBox(height: AppSpacing.lg),
          Container(
            padding: const EdgeInsets.all(AppSpacing.md),
            decoration: BoxDecoration(
              color: AppColors.brandSoft,
              borderRadius: BorderRadius.circular(AppRadius.md),
              border: Border.all(color: AppColors.lightBorder),
            ),
            child: Text(
              'Safety tip: for immediate danger, call your local emergency number '
              '(e.g. police). VERIFIND is a matching aid — not an emergency service '
              'and not a police-station directory.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: AppColors.ink,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.icon,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.lg),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: AppColors.brand, size: 22),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: theme.textTheme.titleSmall),
                const SizedBox(height: 4),
                Text(
                  body,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.65),
                    height: 1.45,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
