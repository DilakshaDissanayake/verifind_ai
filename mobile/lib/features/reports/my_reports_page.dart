import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
      return s == 'active' || s == 'processing' || s == 'pending';
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
                            _ReportCard(
                                  report: items[i],
                                  onClosed: _load,
                                )
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

class _ReportCard extends StatefulWidget {
  const _ReportCard({required this.report, required this.onClosed});
  final Map<String, dynamic> report;
  final VoidCallback onClosed;

  @override
  State<_ReportCard> createState() => _ReportCardState();
}

class _ReportCardState extends State<_ReportCard> {
  bool _closing = false;

  bool get _canClose {
    final s = (widget.report['status'] as String? ?? '').toLowerCase();
    return s != 'closed' && s != 'flagged';
  }

  bool get _isLost {
    final type = widget.report['report_type'] as String? ?? '';
    return type.toUpperCase() == 'LOST';
  }

  Future<void> _confirmClose() async {
    if (_closing || !_canClose) return;
    final isLost = _isLost;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(isLost ? 'You found it yourself?' : 'Take down this listing?'),
        content: Text(
          isLost
              ? 'This hides your lost post from Nearby and matching. '
                    'It is not deleted — admins can still see it. '
                    'Open chats for this listing will close.'
              : 'This hides your found post from Nearby and matching. '
                    'It is not deleted — admins can still see it. '
                    'Open chats for this listing will close.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Keep posted'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(isLost ? 'I found it' : 'Take down'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    await _close();
  }

  Future<void> _close() async {
    final id = widget.report['report_id'] as String? ?? '';
    if (id.isEmpty) return;
    setState(() => _closing = true);
    try {
      final api = context.read<ApiClient>();
      final res = await api.closeReport(
        id,
        reason: _isLost ? 'self_found' : 'withdrawn',
      );
      if (!mounted) return;
      final msg = res['message'] as String? ??
          (_isLost
              ? 'Hidden from Nearby — not deleted.'
              : 'Listing taken down — not deleted.');
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
      widget.onClosed();
    } catch (e) {
      if (!mounted) return;
      setState(() => _closing = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ApiClient.friendlyError(e))),
      );
    }
  }

  void _openAiStatus(String id, String title) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => RepositoryProvider.value(
          value: context.read<ApiClient>(),
          child: AIStatusPage(reportId: id, reportTitle: title),
        ),
      ),
    );
  }

  void _openMatches(String id, String title) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => RepositoryProvider.value(
          value: context.read<ApiClient>(),
          child: MatchesPage(reportId: id, reportTitle: title),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    final id = widget.report['report_id'] as String? ?? '';
    final type = widget.report['report_type'] as String? ?? '';
    final title = widget.report['title'] as String? ?? 'Untitled';
    final category = widget.report['category'] as String?;
    final status = widget.report['status'] as String? ?? 'pending';
    final isLost = _isLost;

    final actions = <_ArcAction>[
      _ArcAction(
        icon: AppIcons.sparkle,
        label: 'AI',
        tooltip: 'AI status',
        onTap: () => _openAiStatus(id, title),
      ),
      _ArcAction(
        icon: AppIcons.matches,
        label: 'Match',
        tooltip: 'Matches',
        onTap: () => _openMatches(id, title),
      ),
      if (_canClose)
        _ArcAction(
          icon: isLost ? AppIcons.checkCircle : AppIcons.trash,
          label: isLost ? 'Found it' : 'Take down',
          tooltip: isLost ? 'I found it myself' : 'Take down listing',
          emphasized: true,
          busy: _closing,
          onTap: _closing ? null : _confirmClose,
        ),
    ];

    return AppCard(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.md,
        AppSpacing.md,
        AppSpacing.sm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: isLost
                      ? statusColors.lost.withValues(alpha: 0.28)
                      : statusColors.mintSoft,
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: Icon(
                  isLost ? AppIcons.lost : AppIcons.found,
                  color: statusColors.ink,
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
                    const SizedBox(height: 6),
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
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          _ActionArc(actions: actions),
        ],
      ),
    );
  }
}

class _ArcAction {
  const _ArcAction({
    required this.icon,
    required this.label,
    required this.tooltip,
    this.onTap,
    this.emphasized = false,
    this.busy = false,
  });

  final IconData icon;
  final String label;
  final String tooltip;
  final VoidCallback? onTap;
  final bool emphasized;
  final bool busy;
}

/// Mini dock on the card: circular slots in a pill track.
class _ActionArc extends StatelessWidget {
  const _ActionArc({required this.actions});
  final List<_ArcAction> actions;

  @override
  Widget build(BuildContext context) {
    final statusColors = Theme.of(context).extension<AppStatusColors>()!;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: statusColors.surfaceAlt,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
        child: Row(
          children: [
            for (final action in actions)
              Expanded(child: _ArcSlot(action: action)),
          ],
        ),
      ),
    );
  }
}

class _ArcSlot extends StatelessWidget {
  const _ArcSlot({required this.action});
  final _ArcAction action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    final fill = action.emphasized ? AppColors.brand : Colors.transparent;
    final iconColor = action.emphasized ? Colors.white : statusColors.ink;

    return Tooltip(
      message: action.tooltip,
      child: InkWell(
        onTap: action.busy
            ? null
            : () {
                HapticFeedback.selectionClick();
                action.onTap?.call();
              },
        borderRadius: BorderRadius.circular(AppRadius.pill),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 36,
                height: 36,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: fill,
                    shape: BoxShape.circle,
                    border: action.emphasized
                        ? null
                        : Border.all(color: statusColors.border, width: 1),
                  ),
                  child: Center(
                    child: action.busy
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : Icon(action.icon, size: 18, color: iconColor),
                  ),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                action.label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.labelSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                  color: action.emphasized
                      ? AppColors.brand
                      : theme.textTheme.bodySmall?.color,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
