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
import '../../widgets/skeleton_loaders.dart';
import '../chat/chat_page.dart';
import '../auth/auth_cubit.dart';
import '../matches/matches_page.dart';
import 'notifications_cubit.dart';

class NotificationsPage extends StatelessWidget {
  const NotificationsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const _NotificationsView();
  }
}

class _NotificationsView extends StatelessWidget {
  const _NotificationsView();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            VfPageHeader(
              eyebrow: 'Stay in the loop',
              title: 'Alerts',
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  BlocBuilder<NotificationsCubit, NotificationsState>(
                    builder: (ctx, state) {
                      final unread = state is NotificationsLoaded
                          ? state.unreadCount
                          : 0;
                      if (unread <= 0) return const SizedBox.shrink();
                      return Container(
                        margin: const EdgeInsets.only(right: 8),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.ink,
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                        ),
                        child: Text(
                          '$unread',
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.white,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      );
                    },
                  ),
                  HeaderIconButton(
                    icon: AppIcons.refresh,
                    tooltip: 'Refresh',
                    onPressed: () => context.read<NotificationsCubit>().load(),
                  ),
                ],
              ),
            ),
            Expanded(
              child: BlocBuilder<NotificationsCubit, NotificationsState>(
                builder: (context, state) {
                  if (state is NotificationsLoading ||
                      state is NotificationsInitial) {
                    return const SkeletonList();
                  }
                  if (state is NotificationsError) {
                    return EmptyState(
                      icon: AppIcons.warningCircle,
                      title: 'Could not load notifications',
                      message: state.message,
                      actionLabel: 'Retry',
                      onAction: () => context.read<NotificationsCubit>().load(),
                    );
                  }
                  if (state is NotificationsLoaded) {
                    if (state.items.isEmpty) {
                      return EmptyState(
                        icon: AppIcons.bellOff,
                        title: 'No notifications yet',
                        message:
                            'When a HIGH or MEDIUM match is found, you\u2019ll be notified here.',
                      );
                    }
                    return ListView.separated(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.xl,
                        AppSpacing.sm,
                        AppSpacing.xl,
                        AppSpacing.dockClearance,
                      ),
                      itemCount: state.items.length,
                      separatorBuilder: (_, __) =>
                          const SizedBox(height: AppSpacing.sm),
                      itemBuilder: (context, i) => _NotifCard(
                        item: state.items[i],
                        onTap: () {
                          final n = state.items[i];
                          final nId = n['notification_id'] as String?;
                          final reportId = n['report_id'] as String?;
                          final chatRoomId = n['chat_room_id'] as String?;
                          final type = n['type'] as String? ?? 'match_found';
                          if (nId != null) {
                            context.read<NotificationsCubit>().markRead(nId);
                          }
                          if ((type == 'chat_ready' ||
                                  type == 'chat_message') &&
                              chatRoomId != null) {
                            final auth = context.read<AuthCubit>().state;
                            final uid = auth is AuthAuthenticated
                                ? auth.userId
                                : null;
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => RepositoryProvider.value(
                                  value: context.read<ApiClient>(),
                                  child: ChatPage(
                                    roomId: chatRoomId,
                                    currentUserId: uid,
                                  ),
                                ),
                              ),
                            );
                            return;
                          }
                          if (reportId != null) {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => RepositoryProvider.value(
                                  value: context.read<ApiClient>(),
                                  child: MatchesPage(reportId: reportId),
                                ),
                              ),
                            );
                          }
                        },
                      ).animate().fadeIn(delay: (i * 45).ms, duration: 280.ms),
                    );
                  }
                  return const SizedBox.shrink();
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NotifCard extends StatelessWidget {
  const _NotifCard({required this.item, required this.onTap});
  final Map<String, dynamic> item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    final band = item['band'] as String? ?? 'LOW';
    final score = ((item['score'] as num?)?.toDouble() ?? 0.0) * 100;
    final isRead = item['is_read'] as bool? ?? false;
    final distM = (item['distance_m'] as num?)?.toDouble();
    final type = item['type'] as String? ?? 'match_found';

    late final Color color;
    late final IconData icon;
    if (type == 'chat_ready' || type == 'chat_message') {
      color = statusColors.success;
      icon = AppIcons.chat;
    } else {
      switch (band) {
        case 'HIGH':
          color = statusColors.success;
          icon = AppIcons.checkCircle;
        case 'MEDIUM':
          color = statusColors.warning;
          icon = AppIcons.warningCircle;
        default:
          color = statusColors.info;
          icon = AppIcons.target;
      }
    }

    return AppCard(
      onTap: onTap,
      color: isRead ? Colors.white : color.withValues(alpha: 0.10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.22),
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: Icon(icon, color: AppColors.ink, size: 20),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  type == 'chat_ready'
                      ? 'Chat ready \u00b7 tap to open'
                      : type == 'chat_message'
                      ? 'New message \u00b7 tap to open'
                      : '$band match \u00b7 ${score.toStringAsFixed(0)}%',
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: isRead ? FontWeight.w600 : FontWeight.w800,
                  ),
                ),
                if (distM != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    distM >= 1000
                        ? '${(distM / 1000).toStringAsFixed(2)} km away'
                        : '${distM.toStringAsFixed(0)} m away',
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ],
            ),
          ),
          if (!isRead)
            Container(
              width: 9,
              height: 9,
              margin: const EdgeInsets.only(top: 4),
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
        ],
      ),
    );
  }
}
