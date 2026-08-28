import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../design/app_colors.dart';
import '../design/app_icons.dart';
import '../design/app_spacing.dart';

class NearbyMapItem {
  const NearbyMapItem({
    required this.reportId,
    required this.lat,
    required this.lon,
    required this.isLost,
  });

  final String reportId;
  final double lat;
  final double lon;
  final bool isLost;
}

class PrivacyNearbyMap extends StatefulWidget {
  const PrivacyNearbyMap({
    super.key,
    required this.centerLat,
    required this.centerLon,
    required this.items,
    this.selectedReportId,
    this.onSelect,
    this.privacyRadiusM = 500,
    this.searchRadiusM = 5000,
  });

  final double centerLat;
  final double centerLon;
  final List<NearbyMapItem> items;
  final String? selectedReportId;
  final ValueChanged<String>? onSelect;
  final double privacyRadiusM;
  final double searchRadiusM;

  @override
  State<PrivacyNearbyMap> createState() => _PrivacyNearbyMapState();
}

class _PrivacyNearbyMapState extends State<PrivacyNearbyMap> {
  final _controller = MapController();

  LatLng get _center => LatLng(widget.centerLat, widget.centerLon);

  @override
  void didUpdateWidget(covariant PrivacyNearbyMap oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.centerLat != widget.centerLat ||
        oldWidget.centerLon != widget.centerLon) {
      _controller.move(_center, 13.4);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final you = _center;
    return FlutterMap(
      mapController: _controller,
      options: MapOptions(
        initialCenter: you,
        initialZoom: 13.4,
        minZoom: 11,
        maxZoom: 16,
        interactionOptions: const InteractionOptions(
          flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
        ),
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
              point: you,
              radius: widget.searchRadiusM,
              useRadiusInMeter: true,
              color: AppColors.brand.withValues(alpha: 0.05),
              borderColor: AppColors.ink.withValues(alpha: 0.18),
              borderStrokeWidth: 1.4,
            ),
            CircleMarker(
              point: you,
              radius: widget.privacyRadiusM,
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
              point: you,
              width: 28,
              height: 28,
              child: Container(
                decoration: BoxDecoration(
                  color: AppColors.brand,
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.white, width: 2.5),
                  boxShadow: AppShadows.soft(),
                ),
              ),
            ),
            ...widget.items.map((item) {
              final selected = item.reportId == widget.selectedReportId;
              final color = item.isLost ? AppColors.lost : AppColors.found;
              return Marker(
                point: LatLng(item.lat, item.lon),
                width: selected ? 40 : 32,
                height: selected ? 40 : 32,
                child: GestureDetector(
                  onTap: () => widget.onSelect?.call(item.reportId),
                  child: Icon(
                    AppIcons.mapPin,
                    size: selected ? 36 : 28,
                    color: color,
                    shadows: const [
                      Shadow(color: Colors.white, blurRadius: 6),
                    ],
                  ),
                ),
              );
            }),
          ],
        ),
        const SimpleAttributionWidget(
          source: Text('OpenStreetMap · CARTO'),
          alignment: Alignment.topRight,
        ),
      ],
    );
  }
}
