import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../core/api_client.dart';
import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';
import '../../widgets/app_card.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/page_header.dart';
import '../../widgets/pill_selector.dart';
import '../../widgets/skeleton_loaders.dart';
import '../../widgets/status_pill.dart';
import '../auth/auth_cubit.dart';
import '../auth/account_status_cubit.dart';
import '../matches/matches_page.dart';
import '../onboarding/privacy_policy_page.dart';
import '../reports/ai_status_page.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _me;
  List<Map<String, dynamic>> _reports = [];
  String _filter = 'LOST';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = context.read<ApiClient>();
      final me = await api.getMe();
      final reports = await api.listMyReports(limit: 100);
      if (!mounted) return;
      setState(() {
        _me = me;
        _reports = List<Map<String, dynamic>>.from(
          (reports['items'] as List? ?? []).map(
            (e) => Map<String, dynamic>.from(e as Map),
          ),
        );
      });
      try {
        context.read<AccountStatusCubit>().refresh(silent: true);
      } catch (_) {}
    } catch (e) {
      if (mounted) {
        setState(() => _error = ApiClient.friendlyError(e));
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  List<Map<String, dynamic>> get _filtered => _reports
      .where((r) => (r['report_type'] as String? ?? '') == _filter)
      .toList();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final auth = context.watch<AuthCubit>().state;
    final email =
        _me?['email'] as String? ??
        (auth is AuthAuthenticated ? auth.email : '');
    final name = _me?['display_name'] as String? ?? email.split('@').first;
    final lost = _me?['lost_count'] as int? ?? 0;
    final found = _me?['found_count'] as int? ?? 0;
    final chats = _me?['active_chats'] as int? ?? 0;
    final isActive = _me?['is_active'] as bool? ?? true;

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: _loading
            ? const SkeletonList()
            : _error != null
            ? EmptyState(
                icon: AppIcons.warningCircle,
                title: 'Could not load profile',
                message: _error,
                actionLabel: 'Retry',
                onAction: _load,
              )
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.xl,
                    AppSpacing.md,
                    AppSpacing.xl,
                    AppSpacing.dockClearance,
                  ),
                  children: [
                    if (!isActive) ...[
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(AppSpacing.md),
                        decoration: BoxDecoration(
                          color: Theme.of(context)
                              .extension<AppStatusColors>()!
                              .danger
                              .withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(AppRadius.md),
                          border: Border.all(
                            color: Theme.of(context)
                                .extension<AppStatusColors>()!
                                .danger
                                .withValues(alpha: 0.5),
                          ),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(
                              AppIcons.warningCircle,
                              color: Theme.of(context)
                                  .extension<AppStatusColors>()!
                                  .danger,
                            ),
                            const SizedBox(width: AppSpacing.sm),
                            Expanded(
                              child: Text(
                                'Account is blocked. Contact an administrator.',
                                style: TextStyle(
                                  color: Theme.of(context)
                                      .extension<AppStatusColors>()!
                                      .danger,
                                  fontWeight: FontWeight.w700,
                                  height: 1.35,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                    ],
                    VfPageHeader(
                      eyebrow: 'Your vault',
                      title: name.isEmpty ? 'VERIFIND user' : name,
                      padded: false,
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          HeaderIconButton(
                            icon: AppIcons.refresh,
                            tooltip: 'Refresh',
                            onPressed: _loading ? null : _load,
                          ),
                          const SizedBox(width: 8),
                          HeaderIconButton(
                            icon: AppIcons.signOut,
                            tooltip: 'Sign out',
                            filled: true,
                            onPressed: () => context.read<AuthCubit>().logout(),
                          ),
                        ],
                      ),
                    ),
                    AppCard(
                      tone: AppCardTone.ink,
                      child: Row(
                        children: [
                          CircleAvatar(
                            radius: 32,
                            backgroundColor: AppColors.brand,
                            child: Icon(
                              AppIcons.user,
                              size: 32,
                              color: AppColors.ink,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.lg),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Signed in',
                                  style: theme.textTheme.labelSmall?.copyWith(
                                    color: Colors.white.withValues(alpha: 0.55),
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  email,
                                  style: theme.textTheme.titleSmall?.copyWith(
                                    color: Colors.white,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    OutlinedButton.icon(
                      onPressed: () => _showChangePassword(context),
                      icon: Icon(AppIcons.lock, size: 18),
                      label: const Text('Change password'),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    TextButton.icon(
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => const PrivacyPolicyPage(),
                        ),
                      ),
                      icon: Icon(AppIcons.shieldCheck, size: 18),
                      label: const Text('Privacy & safety'),
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    Row(
                      children: [
                        Expanded(
                          child: StatGlance(
                            label: 'Lost',
                            value: '$lost',
                            caption: 'Reports',
                            tone: AppCardTone.peach,
                            icon: AppIcons.lost,
                          ),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: StatGlance(
                            label: 'Found',
                            value: '$found',
                            caption: 'Reports',
                            tone: AppCardTone.mint,
                            icon: AppIcons.found,
                          ),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: StatGlance(
                            label: 'Chats',
                            value: '$chats',
                            caption: 'Active',
                            tone: AppCardTone.ink,
                            icon: AppIcons.chat,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    PillSelector(
                      tabs: const [
                        PillTab(
                          value: 'LOST',
                          label: 'My Lost',
                          icon: AppIcons.lost,
                        ),
                        PillTab(
                          value: 'FOUND',
                          label: 'My Found',
                          icon: AppIcons.found,
                        ),
                      ],
                      selected: _filter,
                      onSelected: (v) => setState(() => _filter = v),
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    if (_filtered.isEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: AppSpacing.xxl),
                        child: EmptyState(
                          icon: _filter == 'LOST'
                              ? AppIcons.lost
                              : AppIcons.found,
                          title: _filter == 'LOST'
                              ? 'No lost reports'
                              : 'No found reports',
                          message:
                              'Reports you create appear here, split by type.',
                        ),
                      )
                    else
                      ..._filtered.map(
                        (r) => Padding(
                          padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                          child: _ProfileReportTile(report: r),
                        ),
                      ),
                  ],
                ),
              ),
      ),
    );
  }

  Future<void> _showChangePassword(BuildContext context) async {
    await showDialog<void>(
      context: context,
      builder: (_) => _ChangePasswordDialog(
        authCubit: context.read<AuthCubit>(),
        messenger: ScaffoldMessenger.of(context),
      ),
    );
  }
}

class _ChangePasswordDialog extends StatefulWidget {
  const _ChangePasswordDialog({
    required this.authCubit,
    required this.messenger,
  });

  final AuthCubit authCubit;
  final ScaffoldMessengerState messenger;

  @override
  State<_ChangePasswordDialog> createState() => _ChangePasswordDialogState();
}

class _ChangePasswordDialogState extends State<_ChangePasswordDialog> {
  late final TextEditingController _currentCtrl;
  late final TextEditingController _newCtrl;
  late final TextEditingController _confirmCtrl;
  final _formKey = GlobalKey<FormState>();
  bool _obscureCurrent = true;
  bool _obscureNew = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _currentCtrl = TextEditingController();
    _newCtrl = TextEditingController();
    _confirmCtrl = TextEditingController();
  }

  @override
  void dispose() {
    _currentCtrl.dispose();
    _newCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!(_formKey.currentState?.validate() ?? false) || _saving) return;
    setState(() => _saving = true);
    try {
      final msg = await widget.authCubit.changePassword(
        currentPassword: _currentCtrl.text,
        newPassword: _newCtrl.text,
      );
      if (!mounted) return;
      Navigator.of(context).pop();
      widget.messenger.showSnackBar(SnackBar(content: Text(msg)));
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ApiClient.friendlyError(e))),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Change password'),
      content: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _currentCtrl,
                obscureText: _obscureCurrent,
                enabled: !_saving,
                decoration: InputDecoration(
                  labelText: 'Current password',
                  prefixIcon: Icon(AppIcons.lock, size: 20),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _obscureCurrent ? AppIcons.eye : AppIcons.eyeSlash,
                      size: 20,
                    ),
                    onPressed: () =>
                        setState(() => _obscureCurrent = !_obscureCurrent),
                  ),
                ),
                validator: (v) =>
                    (v == null || v.length < 6) ? 'Required' : null,
              ),
              const SizedBox(height: AppSpacing.md),
              TextFormField(
                controller: _newCtrl,
                obscureText: _obscureNew,
                enabled: !_saving,
                decoration: InputDecoration(
                  labelText: 'New password',
                  prefixIcon: Icon(AppIcons.lock, size: 20),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _obscureNew ? AppIcons.eye : AppIcons.eyeSlash,
                      size: 20,
                    ),
                    onPressed: () => setState(() => _obscureNew = !_obscureNew),
                  ),
                ),
                validator: (v) {
                  if (v == null || v.length < 6) {
                    return 'At least 6 characters';
                  }
                  if (v == _currentCtrl.text) {
                    return 'Must differ from current password';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppSpacing.md),
              TextFormField(
                controller: _confirmCtrl,
                obscureText: _obscureNew,
                enabled: !_saving,
                decoration: const InputDecoration(
                  labelText: 'Confirm new password',
                  prefixIcon: Icon(AppIcons.lock, size: 20),
                ),
                validator: (v) {
                  if (v != _newCtrl.text) return 'Passwords do not match';
                  return null;
                },
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _saving ? null : _save,
          child: _saving
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Text('Update'),
        ),
      ],
    );
  }
}

class _ProfileReportTile extends StatelessWidget {
  const _ProfileReportTile({required this.report});
  final Map<String, dynamic> report;

  @override
  Widget build(BuildContext context) {
    final id = report['report_id'] as String? ?? '';
    final title = report['title'] as String? ?? 'Untitled';
    final type = report['report_type'] as String? ?? '';
    final status = report['status'] as String? ?? '';
    return AppCard(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: 4,
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
        title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Wrap(
          spacing: 6,
          children: [
            StatusPill.reportType(context, type),
            StatusPill.reportStatus(context, status),
          ],
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: Icon(AppIcons.sparkle, size: 18),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => RepositoryProvider.value(
                    value: context.read<ApiClient>(),
                    child: AIStatusPage(reportId: id, reportTitle: title),
                  ),
                ),
              ),
            ),
            IconButton(
              icon: Icon(AppIcons.matches, size: 18),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => RepositoryProvider.value(
                    value: context.read<ApiClient>(),
                    child: MatchesPage(reportId: id, reportTitle: title),
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
