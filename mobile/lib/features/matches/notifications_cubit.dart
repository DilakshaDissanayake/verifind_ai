import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:verifind_mobile/core/api_client.dart';

abstract class NotificationsState extends Equatable {
  @override
  List<Object?> get props => [];
}

class NotificationsInitial extends NotificationsState {}

class NotificationsLoading extends NotificationsState {}

class NotificationsLoaded extends NotificationsState {
  NotificationsLoaded({
    required this.items,
    required this.unreadCount,
    this.newlyArrived = const [],
  });
  final List<Map<String, dynamic>> items;
  final int unreadCount;
  final List<Map<String, dynamic>> newlyArrived;
  @override
  List<Object?> get props => [items, unreadCount, newlyArrived];
}

class NotificationsError extends NotificationsState {
  NotificationsError(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}

class NotificationsCubit extends Cubit<NotificationsState> {
  NotificationsCubit(this._api) : super(NotificationsInitial());
  final ApiClient _api;
  final Set<String> _seenIds = {};
  bool _bootstrapped = false;

  Future<void> load({bool unreadOnly = false, bool silent = false}) async {
    if (!silent) emit(NotificationsLoading());
    try {
      final data = await _api.getNotifications(unreadOnly: unreadOnly);
      final items = List<Map<String, dynamic>>.from(
        (data['items'] as List? ?? []).map(
          (e) => Map<String, dynamic>.from(e as Map),
        ),
      );
      final unread = data['unread_count'] as int? ?? 0;
      final newlyArrived = <Map<String, dynamic>>[];
      if (!_bootstrapped) {
        for (final item in items) {
          final id = item['notification_id'] as String?;
          if (id != null) _seenIds.add(id);
        }
        _bootstrapped = true;
      } else {
        for (final item in items) {
          final id = item['notification_id'] as String?;
          if (id == null || _seenIds.contains(id)) continue;
          _seenIds.add(id);
          if (item['is_read'] != true) newlyArrived.add(item);
        }
      }
      emit(
        NotificationsLoaded(
          items: items,
          unreadCount: unread,
          newlyArrived: newlyArrived,
        ),
      );
    } catch (e) {
      if (!silent) emit(NotificationsError(ApiClient.friendlyError(e)));
    }
  }

  Future<void> markRead(String notificationId) async {
    try {
      await _api.markNotificationRead(notificationId);
      final current = state;
      if (current is NotificationsLoaded) {
        final items = current.items.map((item) {
          if (item['notification_id'] != notificationId) return item;
          return {...item, 'is_read': true};
        }).toList();
        final unreadCount = items
            .where((item) => item['is_read'] != true)
            .length;
        emit(NotificationsLoaded(items: items, unreadCount: unreadCount));
      } else {
        await load(silent: true);
      }
    } catch (_) {}
  }
}
