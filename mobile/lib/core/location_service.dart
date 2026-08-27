import 'package:geolocator/geolocator.dart';
import 'package:verifind_mobile/core/gps_fuzz.dart';

/// Product GPS path: OS location → ±500 m fuzz. Never manual lat/lon UX.
class LocationService {
  LocationService({GpsFuzz? fuzz}) : _fuzz = fuzz ?? GpsFuzz(fuzzMeters: 500);

  final GpsFuzz _fuzz;

  Future<({double lat, double lon, double rawLat, double rawLon})> currentFuzzed() async {
    final enabled = await Geolocator.isLocationServiceEnabled();
    if (!enabled) {
      throw StateError('Turn on Location / GPS on your phone');
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied) {
      throw StateError('Location permission denied');
    }
    if (permission == LocationPermission.deniedForever) {
      throw StateError('Location permission permanently denied — enable in Settings');
    }

    final pos = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 20),
      ),
    );
    final fuzzed = _fuzz.fuzz(pos.latitude, pos.longitude);
    return (
      lat: fuzzed.lat,
      lon: fuzzed.lon,
      rawLat: pos.latitude,
      rawLon: pos.longitude,
    );
  }
}
