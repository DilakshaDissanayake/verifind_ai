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

/// Shows real-time AI processing status for a report.
/// Polls /api/v1/reports/{id}/ai-status until both AI artifacts are ready.
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

  @override
  Widget build(BuildContext context) {
    final status = _data?['status'] as String? ?? 'unknown';
    final tags = _data?['tags'] as Map<String, dynamic>?;
    final hasEmbedding = _data?['has_embedding'] as bool? ?? false;
    final hasVision = (tags?['model'] as String?)?.isNotEmpty ?? false;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.reportTitle != null ? 'AI Status' : 'AI Status',
          maxLines: 1,
        ),
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
              padding: const EdgeInsets.all(AppSpacing.lg),
              children: [
                if (widget.reportTitle != null) ...[
                  Text(
                    widget.reportTitle!,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: AppSpacing.xxl),
                ],
                _PipelineCard(
                  status: status,
                  hasVision: hasVision,
                  hasEmbedding: hasEmbedding,
                ).animate().fadeIn(duration: 320.ms),
                const SizedBox(height: AppSpacing.lg),
                if (tags != null)
                  _TagsCard(
                    tags: tags,
                  ).animate().fadeIn(delay: 100.ms, duration: 320.ms)
                else
                  _NoTagsCard(status: status),
                const SizedBox(height: AppSpacing.lg),
                _PollInfo(pollCount: _pollCount),
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
  });

  final String status;
  final bool hasVision;
  final bool hasEmbedding;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ready =
      (status == 'active' || status == 'matched') && hasVision && hasEmbedding;

    TimelineStepState stateFor(bool done, bool blocked) {
      if (done) return TimelineStepState.done;
      if (blocked) return TimelineStepState.pending;
      return TimelineStepState.active;
    }

    final visionState = stateFor(hasVision, status == 'pending');
    final embedState = stateFor(hasEmbedding, !hasVision);
    final readyState = ready
        ? TimelineStepState.done
        : (hasEmbedding ? TimelineStepState.active : TimelineStepState.pending);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                AppIcons.sparkle,
                color: theme.colorScheme.primary,
                size: 18,
              ),
              const SizedBox(width: AppSpacing.sm),
              Text('Dual AI Pipeline', style: theme.textTheme.titleSmall),
              const Spacer(),
              if (ready)
                Text(
                  status == 'matched' ? 'MATCHED' : 'READY',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.extension<AppStatusColors>()!.success,
                    fontWeight: FontWeight.w800,
                  ),
                )
              else
                PulsingIcon(
                  icon: AppIcons.clock,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
                  size: 16,
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          StepTimeline(
            steps: [
              const TimelineStep(
                title: 'Report received',
                subtitle: 'Queued for AI processing',
                state: TimelineStepState.done,
              ),
              TimelineStep(
                title: 'Vision tagging',
                subtitle:
                    'gpt-4o-mini \u00b7 category, brand, colors, mask boxes',
                state: visionState,
              ),
              TimelineStep(
                title: 'Text embedding',
                subtitle: 'text-embedding-3-small \u00b7 1536-dim vector',
                state: embedState,
              ),
              TimelineStep(
                title: ready ? 'Ready for matching' : 'Waiting to finish',
                subtitle: ready ? 'Visible to the matcher & nearby feed' : null,
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
              Text('AI Vision Tags', style: theme.textTheme.titleSmall),
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
              Text(
                '${maskBoxes.length} region(s) blurred for privacy',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: statusColors.danger,
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
                  ? 'Vision tags will appear shortly (usually within ~8s).'
                  : 'No AI tags found for this report.',
              style: theme.textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}

class _PollInfo extends StatelessWidget {
  const _PollInfo({required this.pollCount});
  final int pollCount;

  @override
  Widget build(BuildContext context) {
    if (pollCount <= 0) return const SizedBox.shrink();
    final theme = Theme.of(context);
    return Center(
      child: Text(
        'Auto-refreshing every 3s \u00b7 checked $pollCount time(s)',
        style: theme.textTheme.bodySmall,
      ),
    );
  }
}
