import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
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
import 'ai_status_page.dart';
import 'create_report_page.dart';

class MyReportsPage extends StatefulWidget {
  const MyReportsPage({super.key});

  @override
  State<MyReportsPage> createState() => _MyReportsPageState();
}

class _MyReportsPageState extends State<MyReportsPage> {
  List<Map<String, dynamic>> _reports = [];
  bool _loading = true;
  bool _initialLoad = true;
  String? _error;
  String _filter = 'ALL';

  @override
  void initState() {
    super.initState();
    _load();
  }

  List<Map<String, dynamic>> get _filtered {
    if (_filter == 'ALL') return _reports;
    return _reports
        .where((r) => (r['report_type'] as String? ?? '') == _filter)
        .toList();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = context.read<ApiClient>();
      final data = await api.listMyReports();
      setState(() {
        _reports = List<Map<String, dynamic>>.from(
          (data['items'] as List? ?? []).map(
            (e) => Map<String, dynamic>.from(e as Map),
          ),
        );
      });
    } catch (e) {
      setState(() => _error = ApiClient.friendlyError(e));
    } finally {
      setState(() {
        _loading = false;
        _initialLoad = false;
      });
    }
  }

  void _openCreateReport() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => RepositoryProvider.value(
          value: context.read<ApiClient>(),
          child: const CreateReportPage(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final items = _filtered;
    final auth = context.watch<AuthCubit>().state;
    final name = auth is AuthAuthenticated
        ? auth.email.split('@').first
        : 'there';
    final lostN = _reports
        .where((r) => (r['report_type'] as String?) == 'LOST')
        .length;
    final foundN = _reports
        .where((r) => (r['report_type'] as String?) == 'FOUND')
        .length;
    final activeN = _reports.where((r) {
      final s = (r['status'] as String? ?? '').toLowerCase();
      return s == 'active' || s == 'matched' || s == 'closed';
    }).length;

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            VfPageHeader(
              eyebrow: 'Hello, $name',
              title: 'Let\'s recover.',
              trailing: HeaderIconButton(
                icon: AppIcons.refresh,
                tooltip: 'Refresh',
                onPressed: _loading ? null : _load,
              ),
            ),
            if (!_initialLoad && _reports.isNotEmpty)
              SizedBox(
                height: 156,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.xl,
                    0,
                    AppSpacing.xl,
                    AppSpacing.lg,
                  ),
                  children: [
                    SizedBox(
                      width: 160,
                      child: StatGlance(
                        label: 'Lost',
                        value: '$lostN',
                        caption: 'Open reports',
                        tone: AppCardTone.peach,
                        icon: AppIcons.lost,
                        progress: _reports.isEmpty
                            ? 0
                            : lostN / _reports.length,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    SizedBox(
                      width: 160,
                      child: StatGlance(
                        label: 'Found',
                        value: '$foundN',
                        caption: 'Returned trail',
                        tone: AppCardTone.mint,
                        icon: AppIcons.found,
                        progress: _reports.isEmpty
                            ? 0
                            : foundN / _reports.length,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    SizedBox(
                      width: 160,
                      child: StatGlance(
                        label: 'Live',
                        value: '$activeN',
                        caption: 'Ready to match',
                        tone: AppCardTone.ink,
                        icon: AppIcons.sparkle,
                        progress: _reports.isEmpty
                            ? 0
                            : activeN / _reports.length,
                      ),
                    ),
                  ],
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.xl,
                0,
                AppSpacing.xl,
                AppSpacing.md,
              ),
              child: PillSelector(
                tabs: const [
                  PillTab(value: 'ALL', label: 'All'),
                  PillTab(value: 'LOST', label: 'Lost'),
                  PillTab(value: 'FOUND', label: 'Found'),
                ],
                selected: _filter,
                onSelected: (v) => setState(() => _filter = v),
              ),
            ),
            Expanded(
              child: _initialLoad
                  ? const SkeletonList()
                  : _error != null
                  ? EmptyState(
                      icon: AppIcons.warningCircle,
                      title: 'Could not load reports',
                      message: _error,
                      actionLabel: 'Retry',
                      onAction: _load,
                    )
                  : items.isEmpty
                  ? EmptyState(
                      icon: AppIcons.myReports(),
                      title: 'No reports yet',
                      message:
                          'File a lost or found report to get AI matching started.',
                      actionLabel: 'Create your first report',
                      onAction: _openCreateReport,
                    )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.separated(
                        padding: const EdgeInsets.fromLTRB(
                          AppSpacing.xl,
                          AppSpacing.sm,
                          AppSpacing.xl,
                          AppSpacing.dockClearance,
                        ),
                        itemCount: items.length,
                        separatorBuilder: (_, __) =>
                            const SizedBox(height: AppSpacing.md),
                        itemBuilder: (context, i) =>
                            _ReportCard(report: items[i])
                                .animate()
                                .fadeIn(delay: (i * 40).ms, duration: 280.ms)
                                .slideY(
                                  begin: 0.06,
                                  end: 0,
                                  curve: Curves.easeOutCubic,
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

class _ReportCard extends StatelessWidget {
  const _ReportCard({required this.report});
  final Map<String, dynamic> report;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final id = report['report_id'] as String? ?? '';
    final type = report['report_type'] as String? ?? '';
    final title = report['title'] as String? ?? 'Untitled';
    final category = report['category'] as String?;
    final status = report['status'] as String? ?? 'pending';
    final isLost = type.toUpperCase() == 'LOST';

    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: isLost
                  ? AppColors.lost.withValues(alpha: 0.35)
                  : AppColors.brandSoft,
              borderRadius: BorderRadius.circular(AppRadius.md),
            ),
            alignment: Alignment.center,
            child: Icon(
              isLost ? AppIcons.lost : AppIcons.found,
              color: AppColors.ink,
              size: 22,
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: theme.textTheme.titleSmall,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: AppSpacing.xs,
                  runSpacing: AppSpacing.xs,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    StatusPill.reportType(context, type),
                    StatusPill.reportStatus(context, status),
                    if (category != null)
                      Text(category, style: theme.textTheme.bodySmall),
                  ],
                ),
              ],
            ),
          ),
          Column(
            children: [
              IconButton(
                icon: Icon(AppIcons.sparkle, size: 20),
                tooltip: 'AI Status',
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
                icon: Icon(AppIcons.matches, size: 20),
                tooltip: 'Matches',
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
        ],
      ),
    );
  }
}
