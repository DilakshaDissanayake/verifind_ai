import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../core/api_client.dart';
import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';
import '../../widgets/app_card.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/step_timeline.dart';
import '../auth/auth_cubit.dart';
import '../matches/matches_page.dart';

/// Live dual-pipeline status. Polls until vision tags and text embedding exist.
class AIStatusPage extends StatefulWidget {
  const AIStatusPage({super.key, required this.reportId, this.reportTitle});

  final String reportId;
  final String? reportTitle;

  @override
  State<AIStatusPage> createState() => _AIStatusPageState();
}

class _AIStatusPageState extends State<AIStatusPage> {
  Map<String, dynamic>? _data;
  String? _error;
  bool _loading = true;
  Timer? _pollTimer;
  int _pollCount = 0;
  final _startedAt = DateTime.now();
  static const _maxPolls = 20;
  static const _pollInterval = Duration(seconds: 3);

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _fetch() async {
    try {
      final api = context.read<ApiClient>();
      final res = await api.getAIStatus(widget.reportId);
      if (!mounted) return;
      final status = res['status'] as String? ?? '';
      setState(() {
        _data = res;
        _loading = false;
        _error = null;
      });
      final tags = res['tags'] as Map?;
      final model = tags?['model'] as String?;
      final hasVision = model != null && model.isNotEmpty;
      final hasEmbedding = res['has_embedding'] as bool? ?? false;
      final aiIncomplete = !hasVision || !hasEmbedding;
      if ((status == 'pending' || status == 'processing' || aiIncomplete) &&
          _pollCount < _maxPolls) {
        _pollCount++;
        _pollTimer?.cancel();
        _pollTimer = Timer(_pollInterval, _fetch);
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = ApiClient.friendlyError(e);
        _loading = false;
      });
    }
  }

  void _openMatches() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => RepositoryProvider.value(
          value: context.read<ApiClient>(),
          child: BlocProvider.value(
            value: context.read<AuthCubit>(),
            child: MatchesPage(
              reportId: widget.reportId,
              reportTitle: widget.reportTitle,
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final status = _data?['status'] as String? ?? 'unknown';
    final tags = _data?['tags'] as Map<String, dynamic>?;
    final hasEmbedding = _data?['has_embedding'] as bool? ?? false;
    final hasVision = (tags?['model'] as String?)?.isNotEmpty ?? false;
    final ready =
        (status == 'active' || status == 'matched') &&
        hasVision &&
        hasEmbedding;

    return Scaffold(
      appBar: AppBar(
        title: const Text('AI pipeline', maxLines: 1),
        actions: [
          IconButton(
            icon: Icon(AppIcons.refresh),
            onPressed: () {
              _pollTimer?.cancel();
              _pollCount = 0;
              setState(() => _loading = true);
              _fetch();
            },
          ),
        ],
      ),
      body: _loading && _data == null
          ? const Center(child: CircularProgressIndicator())
          : _error != null && _data == null
          ? EmptyState(
              icon: AppIcons.warningCircle,
              title: 'Could not load AI status',
              message: _error,
            )
          : ListView(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.lg,
                AppSpacing.md,
                AppSpacing.lg,
                AppSpacing.xxxl,
              ),
              children: [
                if (widget.reportTitle != null) ...[
                  Text(
                    widget.reportTitle!,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                ],
                _HeroProgress(
                  status: status,
                  hasVision: hasVision,
                  hasEmbedding: hasEmbedding,
                  ready: ready,
                  startedAt: _startedAt,
                ).animate().fadeIn(duration: 320.ms),
                const SizedBox(height: AppSpacing.lg),
                _DualEngineCard(
                  hasVision: hasVision,
                  hasEmbedding: hasEmbedding,
                ).animate().fadeIn(delay: 60.ms, duration: 320.ms),
                const SizedBox(height: AppSpacing.lg),
                _PipelineCard(
                  status: status,
                  hasVision: hasVision,
                  hasEmbedding: hasEmbedding,
                  hasTags: tags != null,
                  ready: ready,
                ).animate().fadeIn(delay: 100.ms, duration: 320.ms),
                const SizedBox(height: AppSpacing.lg),
                if (tags != null)
                  _TagsCard(
                    tags: tags,
                  ).animate().fadeIn(delay: 140.ms, duration: 320.ms)
                else
                  _NoTagsCard(status: status),
                if (ready) ...[
                  const SizedBox(height: AppSpacing.xl),
                  FilledButton.icon(
                    onPressed: _openMatches,
                    icon: Icon(AppIcons.matches, size: 18),
                    label: Text(
                      status == 'matched'
                          ? 'View matches'
                          : 'Open matcher',
                    ),
                  ),
                ],
              ],
            ),
    );
  }
}

double _pipelineProgress({
  required bool hasVision,
  required bool hasEmbedding,
  required bool ready,
}) {
  if (ready) return 1;
  var value = 0.12;
  if (hasVision) value += 0.34;
  if (hasEmbedding) value += 0.34;
  if (hasVision && hasEmbedding) value = 0.88;
  return value.clamp(0.0, 1.0);
}

class _HeroProgress extends StatelessWidget {
  const _HeroProgress({
    required this.status,
    required this.hasVision,
    required this.hasEmbedding,
    required this.ready,
    required this.startedAt,
  });

  final String status;
  final bool hasVision;
  final bool hasEmbedding;
  final bool ready;
  final DateTime startedAt;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    final progress = _pipelineProgress(
      hasVision: hasVision,
      hasEmbedding: hasEmbedding,
      ready: ready,
    );
    final elapsed = DateTime.now().difference(startedAt).inSeconds;
    final headline = ready
        ? (status == 'matched' ? 'Matches are ready' : 'Ready for matching')
        : 'Dual AI is reading this report';
    final sub = ready
        ? 'Vision tags and text embedding are in. Public photos stay sanitized.'
        : 'Vision and text run at the same time \u2014 usually about 8 seconds.';

    return AppCard(
      tone: AppCardTone.ink,
      child: Row(
        children: [
          ConfidenceRing(
            value: progress,
            size: 72,
            stroke: 7,
            color: ready ? statusColors.success : AppColors.brandLight,
            trackColor: Colors.white.withValues(alpha: 0.12),
            child: ready
                ? Icon(AppIcons.checkCircle, color: Colors.white, size: 22)
                : Text(
                    '${(progress * 100).round()}%',
                    style: theme.textTheme.labelLarge?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
          ),
          const SizedBox(width: AppSpacing.lg),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  headline,
                  style: theme.textTheme.titleMedium?.copyWith(
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  sub,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: Colors.white.withValues(alpha: 0.7),
                  ),
                ),
                if (!ready && elapsed > 0) ...[
                  const SizedBox(height: 8),
                  Text(
                    'Running \u00b7 ${elapsed}s',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: AppColors.brandLight,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DualEngineCard extends StatelessWidget {
  const _DualEngineCard({
    required this.hasVision,
    required this.hasEmbedding,
  });

  final bool hasVision;
  final bool hasEmbedding;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(AppIcons.sparkle, color: theme.colorScheme.primary, size: 18),
              const SizedBox(width: AppSpacing.sm),
              Text('Dual engine', style: theme.textTheme.titleSmall),
              const Spacer(),
              Text(
                'in parallel',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: AppColors.brand,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: _EngineLane(
                  icon: AppIcons.brain,
                  title: 'Vision',
                  subtitle: hasVision
                      ? 'Category, brand, colors'
                      : 'Reading the photo\u2026',
                  done: hasVision,
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                child: Icon(
                  AppIcons.matches,
                  size: 16,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.35),
                ),
              ),
              Expanded(
                child: _EngineLane(
                  icon: AppIcons.tag,
                  title: 'Text',
                  subtitle: hasEmbedding
                      ? '1536-d embedding ready'
                      : 'Building the vector\u2026',
                  done: hasEmbedding,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _EngineLane extends StatelessWidget {
  const _EngineLane({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.done,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final bool done;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: done
            ? statusColors.success.withValues(alpha: 0.08)
            : AppColors.brandSoft,
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                icon,
                size: 16,
                color: done ? statusColors.success : AppColors.brand,
              ),
              const Spacer(),
              if (done)
                Icon(AppIcons.checkCircle, size: 16, color: statusColors.success)
              else
                SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.8,
                    color: AppColors.brand,
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(title, style: theme.textTheme.titleSmall),
          const SizedBox(height: 2),
          Text(subtitle, style: theme.textTheme.bodySmall),
        ],
      ),
    );
  }
}

class _PipelineCard extends StatelessWidget {
  const _PipelineCard({
    required this.status,
    required this.hasVision,
    required this.hasEmbedding,
    required this.hasTags,
    required this.ready,
  });

  final String status;
  final bool hasVision;
  final bool hasEmbedding;
  final bool hasTags;
  final bool ready;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    TimelineStepState engineState(bool done) {
      if (done) return TimelineStepState.done;
      return TimelineStepState.active;
    }

    final privacyState = hasTags
        ? TimelineStepState.done
        : (hasVision ? TimelineStepState.active : TimelineStepState.pending);
    final readyState = ready
        ? TimelineStepState.done
        : (hasVision && hasEmbedding
              ? TimelineStepState.active
              : TimelineStepState.pending);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                AppIcons.shieldCheck,
                color: theme.colorScheme.primary,
                size: 18,
              ),
              const SizedBox(width: AppSpacing.sm),
              Text('Pipeline steps', style: theme.textTheme.titleSmall),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          StepTimeline(
            steps: [
              const TimelineStep(
                title: 'Report received',
                subtitle: 'Queued \u00b7 original photo locked in the vault',
                state: TimelineStepState.done,
              ),
              TimelineStep(
                title: 'Vision tagging',
                subtitle: 'gpt-4o-mini \u00b7 category, brand, mask boxes',
                state: engineState(hasVision),
              ),
              TimelineStep(
                title: 'Text embedding',
                subtitle: 'text-embedding-3-small \u00b7 runs with vision',
                state: engineState(hasEmbedding),
              ),
              TimelineStep(
                title: 'Privacy sanitization',
                subtitle: 'Unique marks blurred before the public feed',
                state: privacyState,
              ),
              TimelineStep(
                title: ready ? 'Ready for matching' : 'Waiting to finish',
                subtitle: ready
                    ? (status == 'matched'
                          ? 'Visible to the matcher'
                          : 'Visible to the matcher & nearby feed')
                    : null,
                state: readyState,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _TagsCard extends StatelessWidget {
  const _TagsCard({required this.tags});
  final Map<String, dynamic> tags;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    final colors = (tags['colors'] as List?)?.cast<String>() ?? [];
    final maskBoxes = (tags['mask_boxes'] as List?) ?? [];
    final attrs = tags['attributes'] as Map<String, dynamic>? ?? {};

    final chips = <String>[
      if (tags['category'] != null) 'Category: ${tags['category']}',
      if (tags['brand'] != null) 'Brand: ${tags['brand']}',
      ...colors.map((c) => 'Color: $c'),
      if (attrs['model'] != null) 'Model: ${attrs['model']}',
      if (attrs['condition'] != null) 'Condition: ${attrs['condition']}',
      if (attrs['distinctive_features'] != null)
        'Features: ${attrs['distinctive_features']}',
    ];

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(AppIcons.brain, color: theme.colorScheme.primary, size: 18),
              const SizedBox(width: AppSpacing.sm),
              Text('What the AI saw', style: theme.textTheme.titleSmall),
              const Spacer(),
              if (tags['model'] != null)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(AppRadius.pill),
                  ),
                  child: Text(
                    tags['model'] as String,
                    style: theme.textTheme.labelSmall,
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          if (chips.isEmpty)
            Text(
              tags['model'] is String && (tags['model'] as String).isNotEmpty
                  ? 'No descriptive tags extracted.'
                  : 'Vision tagging did not return usable tags.',
              style: theme.textTheme.bodySmall,
            )
          else
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: chips
                  .map(
                    (c) => Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(AppRadius.pill),
                      ),
                      child: Text(c, style: theme.textTheme.bodySmall),
                    ),
                  )
                  .toList(),
            ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Icon(AppIcons.blur, size: 16, color: statusColors.danger),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  '${maskBoxes.length} region(s) blurred for privacy',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: statusColors.danger,
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

class _NoTagsCard extends StatelessWidget {
  const _NoTagsCard({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final processing = status == 'pending' || status == 'processing';
    return AppCard(
      child: Row(
        children: [
          if (processing)
            PulsingIcon(
              icon: AppIcons.sparkle,
              color: theme.colorScheme.primary,
            )
          else
            Icon(
              AppIcons.tag,
              color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
            ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Text(
              processing
                  ? 'Vision tags will appear here when the photo is catalogued.'
                  : 'No AI tags found for this report.',
              style: theme.textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}
