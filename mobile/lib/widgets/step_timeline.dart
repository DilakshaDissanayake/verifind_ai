import 'package:flutter/material.dart';

import '../design/app_colors.dart';
import '../design/app_spacing.dart';

enum TimelineStepState { done, active, pending }

class TimelineStep {
  const TimelineStep({required this.title, this.subtitle, required this.state});
  final String title;
  final String? subtitle;
  final TimelineStepState state;
}

/// Vertical pipeline/progress timeline — used for AI processing status and
/// the claim/verification flow, replacing stacked disconnected cards with a
/// single narrative of "what's happening now".
class StepTimeline extends StatelessWidget {
  const StepTimeline({super.key, required this.steps});

  final List<TimelineStep> steps;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;

    return Column(
      children: List.generate(steps.length, (i) {
        final step = steps[i];
        final isLast = i == steps.length - 1;
        final color = switch (step.state) {
          TimelineStepState.done => statusColors.success,
          TimelineStepState.active => theme.colorScheme.primary,
          TimelineStepState.pending => theme.colorScheme.onSurface.withValues(
            alpha: 0.28,
          ),
        };

        return IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Column(
                children: [
                  _StepDot(color: color, state: step.state),
                  if (!isLast)
                    Expanded(
                      child: Container(
                        width: 2,
                        margin: const EdgeInsets.symmetric(vertical: 2),
                        color: step.state == TimelineStepState.pending
                            ? theme.colorScheme.outline.withValues(alpha: 0.5)
                            : statusColors.success.withValues(alpha: 0.45),
                      ),
                    ),
                ],
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Padding(
                  padding: EdgeInsets.only(bottom: isLast ? 0 : AppSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        step.title,
                        style: theme.textTheme.titleSmall?.copyWith(
                          color: step.state == TimelineStepState.pending
                              ? theme.colorScheme.onSurface.withValues(
                                  alpha: 0.5,
                                )
                              : theme.colorScheme.onSurface,
                        ),
                      ),
                      if (step.subtitle != null) ...[
                        const SizedBox(height: 2),
                        Text(step.subtitle!, style: theme.textTheme.bodySmall),
                      ],
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      }),
    );
  }
}

class _StepDot extends StatelessWidget {
  const _StepDot({required this.color, required this.state});
  final Color color;
  final TimelineStepState state;

  @override
  Widget build(BuildContext context) {
    if (state == TimelineStepState.active) {
      return SizedBox(
        width: 22,
        height: 22,
        child: Stack(
          alignment: Alignment.center,
          children: [
            SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(strokeWidth: 2, color: color),
            ),
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
          ],
        ),
      );
    }
    return Container(
      width: 22,
      height: 22,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      child: state == TimelineStepState.done
          ? const Icon(Icons.check, size: 14, color: Colors.white)
          : null,
    );
  }
}

/// Small pulsing badge for "processing" states (AI pipeline running).
class PulsingIcon extends StatefulWidget {
  const PulsingIcon({
    super.key,
    required this.icon,
    required this.color,
    this.size = 20,
  });
  final IconData icon;
  final Color color;
  final double size;

  @override
  State<PulsingIcon> createState() => _PulsingIconState();
}

class _PulsingIconState extends State<PulsingIcon>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1100),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: Tween(
        begin: 0.4,
        end: 1.0,
      ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeInOut)),
      child: Icon(widget.icon, color: widget.color, size: widget.size),
    );
  }
}
