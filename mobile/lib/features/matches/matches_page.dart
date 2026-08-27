import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../core/api_client.dart';
import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';
import '../../widgets/app_card.dart';
import '../../widgets/confidence_meter.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/skeleton_loaders.dart';
import '../../widgets/status_pill.dart';
import '../chat/chat_page.dart';
import '../claim/claim_page.dart';
import '../auth/auth_cubit.dart';
import 'matches_cubit.dart';

class MatchesPage extends StatelessWidget {
  const MatchesPage({super.key, required this.reportId, this.reportTitle});

  final String reportId;
  final String? reportTitle;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (ctx) => MatchesCubit(ctx.read<ApiClient>())..loadMatches(reportId),
      child: _MatchesView(reportId: reportId, reportTitle: reportTitle),
    );
  }
}

class _MatchesView extends StatelessWidget {
  const _MatchesView({required this.reportId, this.reportTitle});

  final String reportId;
  final String? reportTitle;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(reportTitle != null ? 'Matches' : 'Matches', maxLines: 1),
        actions: [
          IconButton(
            icon: Icon(AppIcons.refresh),
            onPressed: () => context.read<MatchesCubit>().loadMatches(reportId),
          ),
        ],
      ),
      body: BlocBuilder<MatchesCubit, MatchesState>(
        builder: (context, state) {
          if (state is MatchesLoading || state is MatchesInitial) {
            return const SkeletonList();
          }
          if (state is MatchesError) {
            return EmptyState(
              icon: AppIcons.warningCircle,
              title: 'Could not load matches',
              message: state.message,
              actionLabel: 'Retry',
              onAction: () => context.read<MatchesCubit>().loadMatches(reportId),
            );
          }
          if (state is MatchesLoaded) {
            if (state.items.isEmpty) {
              return EmptyState(
                icon: AppIcons.target,
                title: 'No matches yet',
                message: 'AI may still be processing this report. Check back soon.',
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.all(AppSpacing.lg),
              itemCount: state.items.length,
              separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.md),
              itemBuilder: (context, i) {
                final item = state.items[i];
                return _MatchCard(
                  item: item,
                  onClaim: () {
                    final a = item['report_a_id'] as String? ?? '';
                    final b = item['report_b_id'] as String? ?? '';
                    final matchId = item['match_id'] as String? ?? '';
                    final foundId = a == reportId ? b : a;
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => RepositoryProvider.value(
                          value: context.read<ApiClient>(),
                          child: ClaimPage(
                            matchId: matchId,
                            foundReportId: foundId,
                            title: 'Verify ownership',
                          ),
                        ),
                      ),
                    );
                  },
                  onOpenChat: (roomId) {
                    final auth = context.read<AuthCubit>().state;
                    final uid = auth is AuthAuthenticated ? auth.userId : null;
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => RepositoryProvider.value(
                          value: context.read<ApiClient>(),
                          child: ChatPage(roomId: roomId, currentUserId: uid),
                        ),
                      ),
                    );
                  },
                ).animate().fadeIn(delay: (i * 60).ms, duration: 300.ms).slideY(
                      begin: 0.06,
                      end: 0,
                      curve: Curves.easeOutCubic,
                    );
              },
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}

class _MatchCard extends StatelessWidget {
  const _MatchCard({
    required this.item,
    required this.onClaim,
    required this.onOpenChat,
  });

  final Map<String, dynamic> item;
  final VoidCallback onClaim;
  final void Function(String roomId) onOpenChat;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    final band = item['band'] as String? ?? 'LOW';
    final score = ((item['score'] as num?)?.toDouble() ?? 0.0);
    final vision = ((item['vision_score'] as num?)?.toDouble() ?? 0.0);
    final text = ((item['text_score'] as num?)?.toDouble() ?? 0.0);
    final geo = ((item['geo_score'] as num?)?.toDouble() ?? 0.0);
    final distM = (item['distance_m'] as num?)?.toDouble();
    final claimStatus = (item['claim_status'] as String? ?? '').toLowerCase();
    final decision = (item['verification_decision'] as String? ?? '').toUpperCase();
    final chatRoomId = item['chat_room_id'] as String?;

    final isPass = claimStatus == 'passed' || decision == 'PASS';
    final isReview = claimStatus == 'review' || decision == 'REVIEW';
    final isBlocked = claimStatus == 'blocked' || decision == 'BLOCK';
    final canClaim = !isPass && !isReview && !isBlocked && (band == 'HIGH' || band == 'MEDIUM');

    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              ConfidenceRing(
                value: score,
                size: 56,
                stroke: 6,
                color: statusColors.band(band),
                child: Text(
                  '${(score * 100).toStringAsFixed(0)}',
                  style: theme.textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        StatusPill.matchBand(context, band),
                        const SizedBox(width: AppSpacing.sm),
                        if (isPass)
                          StatusPill(
                            label: 'PASS',
                            color: statusColors.success,
                            icon: AppIcons.checkCircle,
                          )
                        else if (isReview)
                          StatusPill(
                            label: 'REVIEW',
                            color: statusColors.warning,
                            icon: AppIcons.clock,
                          )
                        else if (isBlocked)
                          StatusPill(
                            label: 'BLOCKED',
                            color: statusColors.danger,
                            icon: AppIcons.xCircle,
                          ),
                      ],
                    ),
                    if (distM != null) ...[
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          Icon(AppIcons.distance, size: 12, color: theme.colorScheme.onSurface.withValues(alpha: 0.5)),
                          const SizedBox(width: 3),
                          Text(
                            distM >= 1000 ? '${(distM / 1000).toStringAsFixed(2)} km' : '${distM.toStringAsFixed(0)} m',
                            style: theme.textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          ConfidenceMeter(value: score, label: 'Overall confidence', height: 10),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(child: _MiniMeter(label: 'Vision', value: vision)),
              const SizedBox(width: AppSpacing.md),
              Expanded(child: _MiniMeter(label: 'Text', value: text)),
              const SizedBox(width: AppSpacing.md),
              Expanded(child: _MiniMeter(label: 'Geo', value: geo)),
            ],
          ),
          if (isPass && chatRoomId != null) ...[
            const SizedBox(height: AppSpacing.lg),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: null,
                    icon: Icon(AppIcons.checkCircle, size: 18, color: statusColors.success),
                    label: Text(
                      'Pass',
                      style: TextStyle(color: statusColors.success, fontWeight: FontWeight.w700),
                    ),
                    style: OutlinedButton.styleFrom(
                      side: BorderSide(color: statusColors.success.withValues(alpha: 0.55)),
                      disabledForegroundColor: statusColors.success,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () => onOpenChat(chatRoomId),
                    icon: Icon(AppIcons.chat, size: 18),
                    label: const Text('Chat'),
                  ),
                ),
              ],
            ),
          ] else if (isPass) ...[
            const SizedBox(height: AppSpacing.lg),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: null,
                    icon: Icon(AppIcons.checkCircle, size: 18, color: statusColors.success),
                    label: Text(
                      'Pass',
                      style: TextStyle(color: statusColors.success, fontWeight: FontWeight.w700),
                    ),
                    style: OutlinedButton.styleFrom(
                      side: BorderSide(color: statusColors.success.withValues(alpha: 0.55)),
                      disabledForegroundColor: statusColors.success,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: null,
                    icon: Icon(AppIcons.chat, size: 18),
                    label: const Text('Chat'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Verified — chat room provisioning\u2026 open Chats tab shortly.',
              style: theme.textTheme.bodySmall,
            ),
          ] else if (isReview) ...[
            const SizedBox(height: AppSpacing.lg),
            Text(
              'Waiting for admin approval\u2026',
              style: theme.textTheme.bodySmall?.copyWith(color: statusColors.warning),
            ),
          ] else if (canClaim) ...[
            const SizedBox(height: AppSpacing.lg),
            FilledButton.icon(
              onPressed: onClaim,
              icon: Icon(AppIcons.shieldCheck, size: 18),
              label: const Text('Claim / Verify'),
            ),
          ],
        ],
      ),
    );
  }
}

class _MiniMeter extends StatelessWidget {
  const _MiniMeter({required this.label, required this.value});
  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: theme.textTheme.bodySmall),
        const SizedBox(height: 4),
        ConfidenceMeter(value: value, height: 5, showPercent: false),
      ],
    );
  }
}
