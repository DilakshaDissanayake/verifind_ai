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
import '../matches/matches_page.dart';
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
