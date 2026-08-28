import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../core/api_client.dart';
import '../../core/location_service.dart';
import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';
import '../../widgets/app_card.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/network_image_frame.dart';
import '../../widgets/page_header.dart';
import '../../widgets/pill_selector.dart';
import '../../widgets/privacy_map.dart';
import '../../widgets/skeleton_loaders.dart';
import '../../widgets/status_pill.dart';
import '../auth/auth_cubit.dart';
import '../chat/chat_page.dart';
import 'create_report_page.dart';

/// Finder browse: nearby LOST posts from other users. Tap "I found this"
/// to create a FOUND report linked to that LOST item.
class NearbyPage extends StatefulWidget {
  const NearbyPage({super.key});
  @override
  State<NearbyPage> createState() => _NearbyPageState();
}

class _NearbyPageState extends State<NearbyPage> {
  final _location = LocationService();
  bool _loading = true;
  bool _initialLoad = true;
  String? _error;
  List<dynamic> _items = [];
  double? _queryLat;
  double? _queryLon;
  String? _selectedId;
  String _viewMode = 'list';

  /// Default: show both LOST + FOUND within radius.
  String? _filter; // null = ALL

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final api = context.read<ApiClient>();
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final loc = await _location.currentFuzzed();
      final res = await api.nearbyReports(
        lat: loc.lat,
        lon: loc.lon,
        radiusM: 5000,
        reportType: _filter,
      );
      if (!mounted) return;
      setState(() {
        _queryLat = loc.lat;
        _queryLon = loc.lon;
        _items = (res['items'] as List?) ?? [];
        if (_selectedId != null &&
            !_items.any(
              (e) => (e as Map)['report_id'] == _selectedId,
            )) {
          _selectedId = null;
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = ApiClient.friendlyError(e);
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
          _initialLoad = false;
        });
      }
    }
  }

  void _reportFoundFor(Map<String, dynamic> item) {
    final lostId = item['report_id'] as String?;
    if (lostId == null) return;
    HapticFeedback.lightImpact();
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => RepositoryProvider.value(
          value: context.read<ApiClient>(),
          child: CreateReportPage(
            initialType: 'FOUND',
            matchedToReportId: lostId,
            matchedTitle: item['title'] as String?,
          ),
        ),
      ),
    );
  }

  void _openChat(String roomId) {
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
  }

  Map<String, dynamic>? _itemById(String id) {
    for (final raw in _items) {
      final item = Map<String, dynamic>.from(raw as Map);
      if (item['report_id'] == id) return item;
    }
    return null;
  }

  void _showPinDetails(String id) {
    final item = _itemById(id);
    if (item == null) return;
    HapticFeedback.selectionClick();
    setState(() => _selectedId = id);
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) {
        return Padding(
          padding: EdgeInsets.fromLTRB(
            AppSpacing.lg,
            0,
            AppSpacing.lg,
            MediaQuery.viewPaddingOf(sheetContext).bottom + AppSpacing.lg,
          ),
          child: _NearbyReportCard(
            item: item,
            onFound: item['report_type'] == 'LOST'
                ? () {
                    Navigator.of(sheetContext).pop();
                    _reportFoundFor(item);
                  }
                : null,
            onOpenChat: (item['chat_room_id'] as String?) != null
                ? () {
                    Navigator.of(sheetContext).pop();
                    _openChat(item['chat_room_id'] as String);
                  }
                : null,
          ),
        );
      },
    );
  }

  List<NearbyMapItem> get _mapItems {
    final out = <NearbyMapItem>[];
    for (final raw in _items) {
      final item = Map<String, dynamic>.from(raw as Map);
      final lat = (item['latitude'] as num?)?.toDouble();
      final lon = (item['longitude'] as num?)?.toDouble();
      final id = item['report_id'] as String?;
      if (lat == null || lon == null || id == null || id.isEmpty) continue;
      out.add(
        NearbyMapItem(
          reportId: id,
          lat: lat,
          lon: lon,
          isLost: (item['report_type'] as String? ?? '') == 'LOST',
        ),
      );
    }
    return out;
  }

  Widget _buildFeed({
    ScrollController? controller,
    required EdgeInsets padding,
  }) {
    if (_initialLoad) {
      return const SkeletonList(feed: true, count: 3);
    }
    if (_error != null) {
      return EmptyState(
        icon: AppIcons.warningCircle,
        title: 'Could not load nearby posts',
        message: _error,
        actionLabel: 'Retry',
        onAction: _load,
      );
    }
    if (_items.isEmpty) {
      return EmptyState(
        icon: AppIcons.nearby(),
        title: 'No nearby posts yet',
        message: _filter == null
            ? 'No lost or found items near you right now.'
            : _filter == 'LOST'
            ? 'No lost items reported near you right now.'
            : 'No found items reported near you right now.',
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        controller: controller,
        padding: padding,
        itemCount: _items.length,
        separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.md),
        itemBuilder: (context, i) {
          final item = Map<String, dynamic>.from(_items[i] as Map);
          final id = item['report_id'] as String?;
          final selected = id != null && id == _selectedId;
          return DecoratedBox(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AppRadius.lg),
              border: selected
                  ? Border.all(color: AppColors.brand, width: 2)
                  : Border.all(color: Colors.transparent, width: 2),
            ),
            child:
                _NearbyReportCard(
                      item: item,
                      onSelect: id == null
                          ? null
                          : () => setState(() => _selectedId = id),
                      onFound: item['report_type'] == 'LOST'
                          ? () => _reportFoundFor(item)
                          : null,
                      onOpenChat: (item['chat_room_id'] as String?) != null
                          ? () => _openChat(item['chat_room_id'] as String)
                          : null,
                    )
                    .animate()
                    .fadeIn(delay: (i * 50).ms, duration: 300.ms)
                    .slideY(
                      begin: 0.06,
                      end: 0,
                      curve: Curves.easeOutCubic,
                    ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            VfPageHeader(
              eyebrow: 'Around you',
              title: 'Nearby finds',
              trailing: HeaderIconButton(
                icon: AppIcons.refresh,
                tooltip: 'Refresh',
                onPressed: _loading ? null : _load,
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.xl,
                0,
                AppSpacing.xl,
                AppSpacing.sm,
              ),
              child: PillSelector(
                tabs: [
                  PillTab(value: 'ALL', label: 'All', icon: AppIcons.nearby()),
                  const PillTab(
                    value: 'LOST',
                    label: 'Lost',
                    icon: AppIcons.lost,
                  ),
                  const PillTab(
                    value: 'FOUND',
                    label: 'Found',
                    icon: AppIcons.found,
                  ),
                ],
                selected: _filter ?? 'ALL',
                onSelected: (v) {
                  setState(() => _filter = v == 'ALL' ? null : v);
                  _load();
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.xl,
                0,
                AppSpacing.xl,
                AppSpacing.sm,
              ),
              child: PillSelector(
                tabs: [
                  PillTab(value: 'list', label: 'List', icon: AppIcons.myReports()),
                  PillTab(value: 'map', label: 'Map', icon: AppIcons.mapPin),
                ],
                selected: _viewMode,
                onSelected: (v) => setState(() => _viewMode = v),
              ),
            ),
            Expanded(
              child: _viewMode == 'map' &&
                      _queryLat != null &&
                      _queryLon != null &&
                      _error == null &&
                      !_initialLoad
                  ? Column(
                      children: [
                        Padding(
                          padding: const EdgeInsets.fromLTRB(
                            AppSpacing.xl,
                            0,
                            AppSpacing.xl,
                            AppSpacing.sm,
                          ),
                          child: Row(
                            children: [
                              Icon(
                                AppIcons.gps,
                                size: 13,
                                color: theme.colorScheme.onSurface.withValues(
                                  alpha: 0.45,
                                ),
                              ),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  '5 km around your phone \u00b7 tap a pin for details',
                                  style: theme.textTheme.bodySmall,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Expanded(
                          child: ClipRRect(
                            borderRadius: const BorderRadius.vertical(
                              top: Radius.circular(AppRadius.xl),
                            ),
                            child: PrivacyNearbyMap(
                              centerLat: _queryLat!,
                              centerLon: _queryLon!,
                              items: _mapItems,
                              selectedReportId: _selectedId,
                              onSelect: _showPinDetails,
                            ),
                          ),
                        ),
                      ],
                    )
                  : _buildFeed(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.xl,
                        AppSpacing.md,
                        AppSpacing.xl,
                        AppSpacing.dockClearance,
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NearbyReportCard extends StatefulWidget {
  const _NearbyReportCard({
    required this.item,
    this.onFound,
    this.onOpenChat,
    this.onSelect,
  });

  final Map<String, dynamic> item;
  final VoidCallback? onFound;
  final VoidCallback? onOpenChat;
  final VoidCallback? onSelect;

  @override
  State<_NearbyReportCard> createState() => _NearbyReportCardState();
}

class _NearbyReportCardState extends State<_NearbyReportCard> {
  final _pageController = PageController();
  int _page = 0;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  List<String> get _urls {
    final raw = widget.item['image_urls'];
    if (raw is! List) return const [];
    return raw.map((e) => e.toString()).where((u) => u.isNotEmpty).toList();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    final item = widget.item;
    final type = item['report_type'] as String? ?? '';
    final title = item['title'] as String? ?? '(no title)';
    final dist = (item['distance_m'] as num?)?.toDouble();
    final status = item['status'] as String? ?? '';
    final claimStatus = (item['claim_status'] as String? ?? '').toLowerCase();
    final decision = (item['verification_decision'] as String? ?? '')
        .toUpperCase();
    final urls = _urls;

    final isPass = claimStatus == 'passed' || decision == 'PASS';
    final isReview = claimStatus == 'review' || decision == 'REVIEW';
    final isBlocked = claimStatus == 'blocked' || decision == 'BLOCK';
    final hasChat = widget.onOpenChat != null;

    return AppCard(
      padding: EdgeInsets.zero,
      onTap: widget.onSelect,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            height: 196,
            child: urls.isEmpty
                ? Container(
                    color: theme.colorScheme.surfaceContainerHighest,
                    alignment: Alignment.center,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          AppIcons.imageBroken,
                          color: theme.colorScheme.onSurface.withValues(
                            alpha: 0.4,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text('Photo pending', style: theme.textTheme.bodySmall),
                      ],
                    ),
                  )
                : Stack(
                    alignment: Alignment.bottomCenter,
                    children: [
                      PageView.builder(
                        controller: _pageController,
                        itemCount: urls.length,
                        onPageChanged: (i) => setState(() => _page = i),
                        itemBuilder: (context, index) {
                          return NetworkImageFrame(
                            url: urls[index],
                            fit: BoxFit.cover,
                            width: double.infinity,
                            height: 196,
                          );
                        },
                      ),
                      Positioned(
                        top: AppSpacing.sm,
                        left: AppSpacing.sm,
                        child: StatusPill.reportType(context, type),
                      ),
                      if (status.isNotEmpty)
                        Positioned(
                          top: AppSpacing.sm,
                          right: AppSpacing.sm,
                          child: StatusPill.reportStatus(context, status),
                        ),
                      if (urls.length > 1)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: List.generate(urls.length, (i) {
                              final active = i == _page;
                              return Container(
                                width: active ? 8 : 6,
                                height: active ? 8 : 6,
                                margin: const EdgeInsets.symmetric(
                                  horizontal: 3,
                                ),
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: active ? Colors.white : Colors.white54,
                                ),
                              );
                            }),
                          ),
                        ),
                    ],
                  ),
          ),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    if (urls.isEmpty) ...[
                      StatusPill.reportType(context, type),
                      const SizedBox(width: AppSpacing.sm),
                      if (status.isNotEmpty) ...[
                        StatusPill.reportStatus(context, status),
                        const SizedBox(width: AppSpacing.sm),
                      ],
                    ],
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
                          if (dist != null) ...[
                            const SizedBox(height: 2),
                            Row(
                              children: [
                                Icon(
                                  AppIcons.distance,
                                  size: 12,
                                  color: theme.colorScheme.onSurface.withValues(
                                    alpha: 0.5,
                                  ),
                                ),
                                const SizedBox(width: 3),
                                Text(
                                  dist >= 1000
                                      ? '${(dist / 1000).toStringAsFixed(2)} km away'
                                      : '${dist.toStringAsFixed(0)} m away',
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
                if (isPass || isReview || isBlocked || hasChat) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Wrap(
                    spacing: AppSpacing.sm,
                    runSpacing: AppSpacing.xs,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      if (isPass)
                        StatusPill(
                          label: 'PASS',
                          color: statusColors.success,
                          icon: AppIcons.checkCircle,
                          dense: true,
                        )
                      else if (isReview)
                        StatusPill(
                          label: 'REVIEW',
                          color: statusColors.warning,
                          icon: AppIcons.clock,
                          dense: true,
                        )
                      else if (isBlocked)
                        StatusPill(
                          label: 'BLOCKED',
                          color: statusColors.danger,
                          icon: AppIcons.xCircle,
                          dense: true,
                        )
                      else if (claimStatus.isNotEmpty)
                        StatusPill(
                          label: claimStatus.toUpperCase(),
                          color: statusColors.info,
                          icon: AppIcons.shieldCheck,
                          dense: true,
                        ),
                      if (hasChat)
                        FilledButton.tonal(
                          style: FilledButton.styleFrom(
                            minimumSize: const Size(0, 36),
                            padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.md,
                            ),
                          ),
                          onPressed: widget.onOpenChat,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(AppIcons.chat, size: 14),
                              const SizedBox(width: 4),
                              const Text(
                                'Chat',
                                style: TextStyle(fontSize: 12),
                              ),
                            ],
                          ),
                        )
                      else if (widget.onFound != null && !isPass && !isReview)
                        FilledButton.tonal(
                          style: FilledButton.styleFrom(
                            minimumSize: const Size(0, 36),
                            padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.md,
                            ),
                          ),
                          onPressed: widget.onFound,
                          child: const Text(
                            'I found this',
                            style: TextStyle(fontSize: 12),
                          ),
                        ),
                    ],
                  ),
                ] else if (widget.onFound != null) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton.tonal(
                      style: FilledButton.styleFrom(
                        minimumSize: const Size(0, 38),
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.md,
                        ),
                      ),
                      onPressed: widget.onFound,
                      child: const Text(
                        'I found this',
                        style: TextStyle(fontSize: 12),
                      ),
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
