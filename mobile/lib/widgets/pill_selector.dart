import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../design/app_colors.dart';
import '../design/app_spacing.dart';

class PillTab {
  const PillTab({required this.value, required this.label, this.icon});
  final String value;
  final String label;
  final IconData? icon;
}

/// Horizontal pill selector (Day / W / M / Y language).
class PillSelector<T extends String> extends StatelessWidget {
  const PillSelector({
    super.key,
    required this.tabs,
    required this.selected,
    required this.onSelected,
  });

  final List<PillTab> tabs;
  final String selected;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        children: tabs.map((tab) {
          final active = tab.value == selected;
          return Expanded(
            child: GestureDetector(
              onTap: () {
                if (active) return;
                HapticFeedback.selectionClick();
                onSelected(tab.value);
              },
              child: AnimatedContainer(
                duration: AppMotion.fast,
                curve: Curves.easeOutCubic,
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: active ? AppColors.ink : Colors.transparent,
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                ),
                alignment: Alignment.center,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (tab.icon != null) ...[
                      Icon(
                        tab.icon,
                        size: 14,
                        color: active ? Colors.white : AppColors.lightInkMuted,
                      ),
                      const SizedBox(width: 6),
                    ],
                    Text(
                      tab.label,
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            color: active ? Colors.white : AppColors.lightInkMuted,
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}
