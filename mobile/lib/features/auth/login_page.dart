import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../core/api_client.dart';
import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';
import '../../widgets/vf_mark.dart';
import '../onboarding/privacy_policy_page.dart';
import 'auth_cubit.dart';
import 'register_page.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _obscure = true;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;

    return Scaffold(
      body: SafeArea(
        child: BlocConsumer<AuthCubit, AuthState>(
          listener: (context, state) {
            if (state is AuthError) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text(_safeLoginError(state.message))),
              );
            }
          },
          builder: (context, state) {
            final loading = state is AuthLoading;
            final error = state is AuthError
                ? _safeLoginError(state.message)
                : null;

            return ListView(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.xl,
                AppSpacing.xxxl,
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
                      child: const VfMark(),
                    )
                    .animate()
                    .fadeIn(duration: 380.ms)
                    .slideY(begin: 0.15, end: 0, curve: Curves.easeOutCubic),
                const SizedBox(height: AppSpacing.xxl),
                Text(
                  'Welcome back',
                  style: theme.textTheme.headlineMedium,
                ).animate().fadeIn(delay: 80.ms, duration: 380.ms),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Sign in to track your lost & found reports.',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                ).animate().fadeIn(delay: 120.ms, duration: 380.ms),
                const SizedBox(height: AppSpacing.xxl),
                if (error != null) ...[
                  _ErrorBanner(message: error, color: statusColors.danger),
                  const SizedBox(height: AppSpacing.lg),
                ],
                TextField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  autocorrect: false,
                  decoration: InputDecoration(
                    labelText: 'Email',
                    prefixIcon: Icon(AppIcons.email, size: 20),
                  ),
                ).animate().fadeIn(delay: 160.ms, duration: 380.ms),
                const SizedBox(height: AppSpacing.md),
                TextField(
                  controller: _password,
                  obscureText: _obscure,
                  decoration: InputDecoration(
                    labelText: 'Password',
                    prefixIcon: Icon(AppIcons.lock, size: 20),
                    suffixIcon: IconButton(
                      icon: Icon(
                        _obscure ? AppIcons.eye : AppIcons.eyeSlash,
                        size: 20,
                      ),
                      onPressed: () => setState(() => _obscure = !_obscure),
                    ),
                  ),
                ).animate().fadeIn(delay: 200.ms, duration: 380.ms),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: loading
                        ? null
                        : () => _showForgotPassword(context),
                    child: const Text('Forgot password?'),
                  ),
                ).animate().fadeIn(delay: 220.ms, duration: 380.ms),
                const SizedBox(height: AppSpacing.md),
                FilledButton(
                  onPressed: loading
                      ? null
                      : () => context.read<AuthCubit>().login(
                          _email.text.trim(),
                          _password.text,
                        ),
                  child: loading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.4,
                            color: Colors.white,
                          ),
                        )
                      : const Text('Sign in'),
                ).animate().fadeIn(delay: 240.ms, duration: 380.ms),
                const SizedBox(height: AppSpacing.md),
                TextButton(
                  onPressed: loading
                      ? null
                      : () => Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => const RegisterPage(),
                          ),
                        ),
                  child: const Text('New here? Create an account'),
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
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.55),
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Future<void> _showForgotPassword(BuildContext context) async {
    final initialEmail = _email.text.trim();
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => _ForgotPasswordDialog(
        initialEmail: initialEmail,
        authCubit: context.read<AuthCubit>(),
        messenger: ScaffoldMessenger.of(context),
      ),
    );
  }
}

/// Owns its [TextEditingController] so Cancel/Send cannot dispose it mid-frame.
class _ForgotPasswordDialog extends StatefulWidget {
  const _ForgotPasswordDialog({
    required this.initialEmail,
    required this.authCubit,
    required this.messenger,
  });

  final String initialEmail;
  final AuthCubit authCubit;
  final ScaffoldMessengerState messenger;

  @override
  State<_ForgotPasswordDialog> createState() => _ForgotPasswordDialogState();
}

class _ForgotPasswordDialogState extends State<_ForgotPasswordDialog> {
  late final TextEditingController _emailCtrl;
  final _formKey = GlobalKey<FormState>();
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    _emailCtrl = TextEditingController(text: widget.initialEmail);
  }

  @override
  void dispose() {
    _emailCtrl.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    if (!(_formKey.currentState?.validate() ?? false) || _sending) return;
    setState(() => _sending = true);
    try {
      final msg = await widget.authCubit.forgotPassword(_emailCtrl.text.trim());
      if (!mounted) return;
      Navigator.of(context).pop();
      widget.messenger.showSnackBar(SnackBar(content: Text(msg)));
    } catch (e) {
      if (!mounted) return;
      setState(() => _sending = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ApiClient.friendlyError(e))),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Reset password'),
      content: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Enter your account email. If it is registered, we will send a reset link.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: AppSpacing.md),
            TextFormField(
              controller: _emailCtrl,
              keyboardType: TextInputType.emailAddress,
              autocorrect: false,
              enabled: !_sending,
              decoration: const InputDecoration(
                labelText: 'Email',
                prefixIcon: Icon(AppIcons.email, size: 20),
              ),
              validator: (v) {
                if (v == null || !v.contains('@')) {
                  return 'Enter a valid email';
                }
                return null;
              },
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _sending ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _sending ? null : _send,
          child: _sending
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Text('Send link'),
        ),
      ],
    );
  }
}

String _safeLoginError(String message) {
  final normalized = message.toLowerCase();
  if (normalized.contains('401') ||
      normalized.contains('invalid email') ||
      normalized.contains('invalid password') ||
      normalized.contains('invalid credential')) {
    return 'Invalid email or password';
  }
  if (normalized.contains('blocked') || normalized.contains('prohibited')) {
    return message;
  }
  if (normalized.contains('not verified') ||
      (normalized.contains('403') && normalized.contains('email'))) {
    return 'Please verify your email before signing in. Use the link in your inbox.';
  }
  if (normalized.contains('403')) {
    return message.length > 8 ? message : 'Access denied. Check account status.';
  }
  return 'Unable to sign in. Check your details and try again.';
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message, required this.color});
  final String message;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppRadius.md),
        boxShadow: AppShadows.soft(),
      ),
      child: Row(
        children: [
          Icon(AppIcons.warningCircle, color: color, size: 18),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(message, style: TextStyle(color: color, fontSize: 13)),
          ),
        ],
      ),
    );
  }
}
