import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../core/location_service.dart';
import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';

class PickedArea {
  const PickedArea({required this.lat, required this.lon});

  final double lat;
  final double lon;
}

/// Tap an approximate area. Result is ±500 m fuzzed. No lat/lon fields.
class PlacePickerPage extends StatefulWidget {
  const PlacePickerPage({super.key, this.initialLat, this.initialLon});

  final double? initialLat;
  final double? initialLon;

  @override
  State<PlacePickerPage> createState() => _PlacePickerPageState();
}

class _PlacePickerPageState extends State<PlacePickerPage> {
  static const _colombo = LatLng(6.9271, 79.8612);

  final _map = MapController();
  final _location = LocationService();
  late LatLng _point;
  bool _locating = false;

  @override
  void initState() {
    super.initState();
    if (widget.initialLat != null && widget.initialLon != null) {
      _point = LatLng(widget.initialLat!, widget.initialLon!);
    } else {
      _point = _colombo;
      _jumpToPhone();
    }
  }

  @override
  void dispose() {
    _map.dispose();
    super.dispose();
  }

  Future<void> _jumpToPhone() async {
    setState(() => _locating = true);
    try {
      final loc = await _location.currentFuzzed();
      if (!mounted) return;
      final next = LatLng(loc.lat, loc.lon);
      setState(() => _point = next);
      _map.move(next, 14);
    } catch (_) {
      // Keep Colombo / last pin — user can still tap the incident area.
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  void _confirm() {
    HapticFeedback.mediumImpact();
    final fuzzed = _location.fuzzPoint(_point.latitude, _point.longitude);
    Navigator.of(context).pop(PickedArea(lat: fuzzed.lat, lon: fuzzed.lon));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Pin the actual place')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.lg,
              AppSpacing.sm,
              AppSpacing.lg,
              AppSpacing.md,
            ),
            child: Text(
              'Tap the map where it happened \u2014 for example Colombo, '
              'even if you are home now. We only save an approximate area '
              '(\u00b1500 m privacy fuzz). Exact GPS is never shown.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
              ),
            ),
          ),
          Expanded(
            child: FlutterMap(
              mapController: _map,
              options: MapOptions(
                initialCenter: _point,
                initialZoom: 13.4,
                minZoom: 8,
                maxZoom: 16,
                interactionOptions: const InteractionOptions(
                  flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
                ),
                onTap: (_, latLng) {
                  HapticFeedback.selectionClick();
                  setState(() => _point = latLng);
                },
              ),
              children: [
                TileLayer(
                  urlTemplate:
                      'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
                  subdomains: const ['a', 'b', 'c', 'd'],
                  userAgentPackageName: 'com.example.nexo_frontend',
                ),
                CircleLayer(
                  circles: [
                    CircleMarker(
                      point: _point,
                      radius: 500,
                      useRadiusInMeter: true,
                      color: AppColors.brand.withValues(alpha: 0.16),
                      borderColor: AppColors.brand.withValues(alpha: 0.55),
                      borderStrokeWidth: 2,
                    ),
                  ],
                ),
                MarkerLayer(
                  markers: [
                    Marker(
                      point: _point,
                      width: 36,
                      height: 36,
                      child: Icon(
                        AppIcons.mapPin,
                        size: 36,
                        color: AppColors.brand,
                      ),
                    ),
                  ],
                ),
                const SimpleAttributionWidget(
                  source: Text('OpenStreetMap · CARTO'),
                  alignment: Alignment.topRight,
                ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          AppSpacing.sm,
          AppSpacing.lg,
          AppSpacing.lg,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            OutlinedButton.icon(
              onPressed: _locating ? null : _jumpToPhone,
              icon: _locating
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Icon(AppIcons.gps, size: 18),
              label: const Text('Jump to my phone area'),
            ),
            const SizedBox(height: AppSpacing.sm),
            FilledButton(
              onPressed: _confirm,
              child: const Text('Use this approximate area'),
            ),
          ],
        ),
      ),
    );
  }
}
