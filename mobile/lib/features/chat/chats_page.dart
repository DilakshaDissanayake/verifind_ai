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
import '../auth/auth_cubit.dart';
import 'chat_page.dart';

/// Lists active anonymous chat rooms for the signed-in user (lost + found).
class ChatsPage extends StatefulWidget {
  const ChatsPage({super.key});

  @override
  State<ChatsPage> createState() => _ChatsPageState();
}

class _ChatsPageState extends State<ChatsPage> {
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _rooms = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = context.read<ApiClient>();
      final data = await api.listChatRooms();
      if (!mounted) return;
      setState(() {
        _rooms = List<Map<String, dynamic>>.from(
          (data['items'] as List? ?? []).map(
            (e) => Map<String, dynamic>.from(e as Map),
          ),
        );
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = ApiClient.friendlyError(e));
    } finally {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  void _openRoom(Map<String, dynamic> room) {
    final roomId = room['room_id'] as String? ?? '';
    if (roomId.isEmpty) return;
    final auth = context.read<AuthCubit>().state;
    final uid = auth is AuthAuthenticated
        ? auth.userId
        : room['viewer_id'] as String?;
    final title = room['title'] as String?;
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => RepositoryProvider.value(
          value: context.read<ApiClient>(),
          child: ChatPage(roomId: roomId, currentUserId: uid, title: title),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            VfPageHeader(
              eyebrow: 'Verified rooms',
              title: 'Chats',
              trailing: HeaderIconButton(
                icon: AppIcons.refresh,
                tooltip: 'Refresh',
                onPressed: _loading ? null : _load,
              ),
            ),
            Expanded(
              child: _loading
                  ? const SkeletonList()
                  : _error != null
                  ? EmptyState(
                      icon: AppIcons.warningCircle,
                      title: 'Could not load chats',
                      message: _error,
                      actionLabel: 'Retry',
                      onAction: _load,
                    )
                  : _rooms.isEmpty
                  ? EmptyState(
                      icon: AppIcons.chat,
                      title: 'No chats yet',
                      message:
                          'After ownership is verified (PASS), both parties get an anonymous chat here.',
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
                        itemCount: _rooms.length,
                        separatorBuilder: (_, __) =>
                            const SizedBox(height: AppSpacing.md),
                        itemBuilder: (context, i) {
                          final room = _rooms[i];
                          final title =
                              room['title'] as String? ?? 'Claim chat';
                          final lost = room['lost_title'] as String?;
                          final found = room['found_title'] as String?;
                          final score = (room['match_score'] as num?)
                              ?.toDouble();
                          final subtitle = [
                            if (lost != null && lost.isNotEmpty) 'Lost: $lost',
                            if (found != null && found.isNotEmpty)
                              'Found: $found',
                            if (score != null)
                              '${(score * 100).toStringAsFixed(0)}% match',
                          ].join(' · ');
                          return AppCard(
                            onTap: () => _openRoom(room),
                            child: Row(
                              children: [
                                CircleAvatar(
                                  radius: 24,
                                  backgroundColor: statusColors.success
                                      .withValues(alpha: 0.18),
                                  child: Icon(
                                    AppIcons.verifiedBadge,
                                    color: AppColors.ink,
                                  ),
                                ),
                                const SizedBox(width: AppSpacing.md),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        title,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: theme.textTheme.titleSmall,
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        subtitle.isEmpty
                                            ? 'Verified · tap to open'
                                            : subtitle,
                                        style: theme.textTheme.bodySmall,
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ],
                                  ),
                                ),
                                Icon(AppIcons.caretRight, size: 16),
                              ],
                            ),
                          ).animate().fadeIn(delay: (i * 40).ms);
                        },
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
