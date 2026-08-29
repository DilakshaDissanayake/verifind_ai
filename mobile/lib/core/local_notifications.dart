import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// OS tray banners while the app is open. No background isolate / FCM service.
class LocalNotifications {
  LocalNotifications._();
  static final LocalNotifications instance = LocalNotifications._();

  final _plugin = FlutterLocalNotificationsPlugin();
  bool _ready = false;
  int _seq = 1;

  bool get _supported =>
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.android ||
          defaultTargetPlatform == TargetPlatform.iOS);

  Future<void> init() async {
    if (!_supported) return;
    try {
      const android = AndroidInitializationSettings('@mipmap/ic_launcher');
      const ios = DarwinInitializationSettings(
        requestAlertPermission: true,
        requestBadgePermission: true,
        requestSoundPermission: true,
      );
      await _plugin.initialize(
        const InitializationSettings(android: android, iOS: ios),
      );
      _ready = true;
      await requestPermission();
    } catch (_) {
      _ready = false;
    }
  }

  Future<void> requestPermission() async {
    if (!_ready) return;
    try {
      final android = _plugin
          .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin
          >();
      await android?.requestNotificationsPermission();
      final ios = _plugin
          .resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin
          >();
      await ios?.requestPermissions(alert: true, badge: true, sound: true);
    } catch (_) {}
  }

  Future<void> showFromItem(Map<String, dynamic> item) async {
    if (!_ready) return;
    final type = item['type'] as String? ?? 'match_found';
    final band = item['band'] as String? ?? '';
    final preview = (item['preview'] as String?)?.trim();
    final distM = (item['distance_m'] as num?)?.toDouble();
    final distLabel = distM == null ? null : _fmtDist(distM);

    late final String title;
    late final String body;
    if (type == 'nearby_post') {
      final kind = band == 'FOUND' ? 'found item' : 'lost item';
      title = 'New $kind nearby';
      if (preview != null && preview.isNotEmpty && distLabel != null) {
        body = '$preview · $distLabel';
      } else if (preview != null && preview.isNotEmpty) {
        body = preview;
      } else {
        body = distLabel ?? 'Within 5 km of you';
      }
    } else if (type == 'chat_message') {
      title = 'New message';
      body = (preview != null && preview.isNotEmpty)
          ? preview
          : 'Someone sent a message';
    } else if (type == 'chat_ready') {
      title = 'Chat is ready';
      body = 'You can message the other person';
    } else {
      title = band.isEmpty ? 'New match' : '$band match found';
      body = distLabel ?? 'Open Alerts for details';
    }

    try {
      await _plugin.show(
        _seq++,
        title,
        body,
        const NotificationDetails(
          android: AndroidNotificationDetails(
            'verifind_alerts',
            'Nearby alerts',
            channelDescription: 'Lost and found posts within 5 km',
            importance: Importance.high,
            priority: Priority.high,
            playSound: true,
          ),
          iOS: DarwinNotificationDetails(
            presentAlert: true,
            presentBadge: true,
            presentSound: true,
          ),
        ),
      );
    } catch (_) {}
  }

  String _fmtDist(double distM) {
    if (distM >= 1000) {
      return '${(distM / 1000).toStringAsFixed(1)} km away';
    }
    return '${distM.toStringAsFixed(0)} m away';
  }
}
