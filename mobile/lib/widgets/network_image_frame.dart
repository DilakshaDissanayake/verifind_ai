import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../design/app_icons.dart';
import 'skeleton_loaders.dart';

/// Wraps [CachedNetworkImage] with a shimmer placeholder and a friendly
/// broken-image fallback, matching Netflix/Uber-grade image loading polish.
class NetworkImageFrame extends StatelessWidget {
  const NetworkImageFrame({
    super.key,
    required this.url,
    this.height,
    this.width,
    this.fit = BoxFit.cover,
  });

  final String url;
  final double? height;
  final double? width;
  final BoxFit fit;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return CachedNetworkImage(
      imageUrl: url,
      height: height,
      width: width,
      fit: fit,
      fadeInDuration: const Duration(milliseconds: 220),
      placeholder: (context, _) => AppShimmer(
        child: Container(color: Colors.white, height: height, width: width),
      ),
      errorWidget: (context, _, __) => Container(
        height: height,
        width: width,
        color: scheme.surfaceContainerHighest,
        alignment: Alignment.center,
        child: Icon(
          AppIcons.imageBroken,
          color: scheme.onSurface.withValues(alpha: 0.4),
        ),
      ),
    );
  }
}
