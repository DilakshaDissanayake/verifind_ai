import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';
import '../../widgets/vf_mark.dart';
import '../onboarding/privacy_policy_page.dart';
import 'auth_cubit.dart';

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});
  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  final _emergencyContact = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _obscure = true;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    _confirm.dispose();
    _emergencyContact.dispose();
    super.dispose();
  }

  void _submit() {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    context.read<AuthCubit>().register(
      _email.text.trim(),
      _password.text,
      displayName: _name.text.trim().isEmpty ? null : _name.text.trim(),
      emergencyContact: _emergencyContact.text.trim(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Create account')),
      body: SafeArea(
        child: BlocConsumer<AuthCubit, AuthState>(
          listener: (context, state) {
            if (state is AuthError) {
              ScaffoldMessenger.of(
                context,
              ).showSnackBar(SnackBar(content: Text('Unable to create account. Please try again.')));
            } else if (state is AuthNeedsConfirmation) {
              _showVerificationDialog(context, state.email, state.message);
            } else if (state is AuthAuthenticated) {
              Navigator.of(context).popUntil((r) => r.isFirst);
            }
          },
          builder: (context, state) {
            final loading = state is AuthLoading;
            return Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.xl,
                  AppSpacing.lg,
                  AppSpacing.xl,
                  AppSpacing.xl,
                ),
                children: [
                  Container(
                    padding: const EdgeInsets.all(AppSpacing.lg),
                    decoration: BoxDecoration(
                      color: AppColors.brandSoft,
                      borderRadius: BorderRadius.circular(AppRadius.lg),
                      border: Border.all(color: AppColors.lightBorder),
                    ),
                    child: const VfMark(size: 40),
                  ).animate().fadeIn(duration: 320.ms),
                  const SizedBox(height: AppSpacing.md),
                  Text(
                    'Join VERIFIND',
                    style: theme.textTheme.headlineMedium,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Create an account to report lost or found items.',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xxl),
                  TextFormField(
                    controller: _name,
                    decoration: InputDecoration(
                      labelText: 'Display name (optional)',
                      prefixIcon: Icon(AppIcons.user, size: 20),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextFormField(
                    controller: _emergencyContact,
                    keyboardType: TextInputType.phone,
                    decoration: InputDecoration(
                      labelText: 'Emergency contact number *',
                      helperText:
                          'Private safety contact for admins only — not a public police directory.',
                      prefixIcon: Icon(AppIcons.phone, size: 20),
                    ),
                    validator: (v) {
                      final value = v?.trim() ?? '';
                      if (value.length < 7) return 'Enter a valid phone number';
                      if (!RegExp(r'^[+0-9 ()-]+$').hasMatch(value)) {
                        return 'Use numbers, spaces, +, or - only';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextFormField(
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    autocorrect: false,
                    decoration: InputDecoration(
                      labelText: 'Email',
                      prefixIcon: Icon(AppIcons.email, size: 20),
                    ),
                    validator: (v) {
                      if (v == null || v.trim().isEmpty) {
                        return 'Email required';
                      }
                      if (!v.contains('@')) return 'Enter a valid email';
                      return null;
                    },
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextFormField(
                    controller: _password,
                    obscureText: _obscure,
                    decoration: InputDecoration(
                      labelText: 'Password (min 6)',
                      prefixIcon: Icon(AppIcons.lock, size: 20),
                      suffixIcon: IconButton(
                        icon: Icon(
                          _obscure ? AppIcons.eye : AppIcons.eyeSlash,
                          size: 20,
                        ),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                    ),
                    validator: (v) {
                      if (v == null || v.length < 6) {
                        return 'At least 6 characters';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextFormField(
                    controller: _confirm,
                    obscureText: _obscure,
                    decoration: InputDecoration(
                      labelText: 'Confirm password',
                      prefixIcon: Icon(AppIcons.shieldCheck, size: 20),
                    ),
                    validator: (v) {
                      if (v != _password.text) return 'Passwords do not match';
                      return null;
                    },
                  ),
                  const SizedBox(height: AppSpacing.xxl),
                  FilledButton(
                    onPressed: loading ? null : _submit,
                    child: loading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.4,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Create account'),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  TextButton(
                    onPressed: loading
                        ? null
                        : () => Navigator.of(context).pop(),
                    child: const Text('Already have an account? Sign in'),
                  ),
                  TextButton(
                    onPressed: loading
                        ? null
                        : () => Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => const PrivacyPolicyPage(),
                            ),
                          ),
                    child: Text(
                      'Privacy & safety',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurface.withValues(
                          alpha: 0.55,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  void _showVerificationDialog(BuildContext context, String email, String message) {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Verify your email'),
        content: Text('$message\n\nWe sent a confirmation link to $email. Verify it before signing in.'),
        actions: [
          TextButton(
            onPressed: () async {
              final ok = await context.read<AuthCubit>().resendVerification(email);
              if (!dialogContext.mounted) return;
              ScaffoldMessenger.of(dialogContext).showSnackBar(
                SnackBar(content: Text(ok ? 'Verification email sent again.' : 'Could not resend yet. Try again shortly.')),
              );
            },
            child: const Text('Resend email'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              Navigator.of(context).pop();
            },
            child: const Text('Back to sign in'),
          ),
        ],
      ),
    );
  }
}
