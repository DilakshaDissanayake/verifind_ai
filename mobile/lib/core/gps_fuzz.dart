import 'dart:math';

/// Client-side GPS fuzz (±[fuzzMeters]) before send — matches config/param.yaml gps.fuzz_meters.
class GpsFuzz {
  GpsFuzz({this.fuzzMeters = 500, Random? rng}) : _rng = rng ?? Random();

  final int fuzzMeters;
  final Random _rng;
  static const double _earthRadiusM = 6371000.0;

  ({double lat, double lon}) fuzz(double lat, double lon) {
    if (fuzzMeters <= 0) return (lat: lat, lon: lon);
    final distance = fuzzMeters * sqrt(_rng.nextDouble());
    final bearing = _rng.nextDouble() * 2 * pi;
    final latRad = lat * pi / 180.0;
    final dLat = (distance * cos(bearing)) / _earthRadiusM;
    final dLon =
        (distance * sin(bearing)) / (_earthRadiusM * max(cos(latRad), 1e-6));
    var newLat = lat + dLat * 180.0 / pi;
    var newLon = lon + dLon * 180.0 / pi;
    newLat = newLat.clamp(-90.0, 90.0);
    newLon = ((newLon + 180.0) % 360.0) - 180.0;
    return (lat: newLat, lon: newLon);
  }
}
