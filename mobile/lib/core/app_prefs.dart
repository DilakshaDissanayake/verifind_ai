import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Small persistence helper for first-run / consent flags.
///
/// Reuses [FlutterSecureStorage] (already a project dependency) so we don't
/// pull in a second key-value package just to remember a couple of booleans.
class AppPrefs {
  AppPrefs({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _kOnboarded = 'onboarding_complete_v1';

  /// Whether the user has finished onboarding + the policy/consent notice.
  Future<bool> hasOnboarded() async {
    final value = await _storage.read(key: _kOnboarded);
    return value == 'true';
  }

  Future<void> setOnboarded() =>
      _storage.write(key: _kOnboarded, value: 'true');
}
