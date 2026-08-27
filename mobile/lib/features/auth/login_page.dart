import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';
import '../../widgets/vf_mark.dart';
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
                const SizedBox(height: AppSpacing.xxl),
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
              ],
            );
          },
        ),
      ),
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
