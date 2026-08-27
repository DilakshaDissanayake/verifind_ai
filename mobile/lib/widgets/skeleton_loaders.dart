import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

import '../design/app_colors.dart';
import '../design/app_spacing.dart';

/// Shimmer wrapper. Apply only around the CONTENT shapes (boxes), not the card
/// container — this ensures the card boundary is always visible on a white page
/// while only the content areas animate.
class AppShimmer extends StatelessWidget {
  const AppShimmer({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<AppStatusColors>()!;
    return Shimmer.fromColors(
      baseColor: colors.shimmerBase,
      highlightColor: colors.shimmerHighlight,
      period: const Duration(milliseconds: 1200),
      child: child,
    );
  }
}

/// A single shimmering content bar. Color is the "shape" that the shimmer
/// gradient paints over — use a mid-gray so there's contrast against the card.
class SkeletonBox extends StatelessWidget {
  const SkeletonBox({
    super.key,
    this.width,
    this.height = 13,
    this.radius = AppRadius.sm,
  });

  final double? width;
  final double height;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<AppStatusColors>()!;
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        // Use shimmerBase as the box color so there's always visible contrast
        // between the animated highlight (#F1F5F9) and this base (#DDE3ED).
        color: colors.shimmerBase,
        borderRadius: BorderRadius.circular(radius),
      ),
    );
  }
}

/// Card frame: sits OUTSIDE the shimmer so the card boundary is always visible.
/// Only the inner SkeletonBoxes are wrapped in AppShimmer.
class _SkeletonCard extends StatelessWidget {
  const _SkeletonCard({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.lightSurface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        border: Border.all(color: AppColors.lightBorder, width: 1),
        boxShadow: AppShadows.soft(),
      ),
      child: child,
    );
  }
}

/// Skeleton for a report/notification card row (avatar + two lines).
class SkeletonListCard extends StatelessWidget {
  const SkeletonListCard({super.key});

  @override
  Widget build(BuildContext context) {
    return _SkeletonCard(
      child: AppShimmer(
        child: Row(
          children: [
            SkeletonBox(width: 48, height: 48, radius: AppRadius.md),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  SkeletonBox(width: MediaQuery.of(context).size.width * 0.42),
                  const SizedBox(height: AppSpacing.sm),
                  const SkeletonBox(width: 80, height: 10),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Skeleton for an image-forward feed card (nearby posts).
class SkeletonFeedCard extends StatelessWidget {
  const SkeletonFeedCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.lightSurface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        border: Border.all(color: AppColors.lightBorder, width: 1),
        boxShadow: AppShadows.soft(),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          AppShimmer(
            child: Container(
              height: 170,
              color: AppColors.lightSurfaceAlt,
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: AppShimmer(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SkeletonBox(width: MediaQuery.of(context).size.width * 0.52),
                  const SizedBox(height: AppSpacing.sm),
                  const SkeletonBox(width: 110, height: 10),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Vertical list of skeleton cards for initial-loading states.
class SkeletonList extends StatelessWidget {
  const SkeletonList({
    super.key,
    this.count = 4,
    this.feed = false,
  });

  final int count;
  final bool feed;

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.xl,
        AppSpacing.lg,
        AppSpacing.xl,
        AppSpacing.dockClearance,
      ),
      physics: const NeverScrollableScrollPhysics(),
      itemCount: count,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.md),
      itemBuilder: (_, __) => feed ? const SkeletonFeedCard() : const SkeletonListCard(),
    );
  }
}
