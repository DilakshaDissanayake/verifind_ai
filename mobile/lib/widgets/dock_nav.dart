import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../design/app_colors.dart';
import '../design/app_icons.dart';
import '../design/app_spacing.dart';

class DockItem {
  const DockItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
    this.badge = 0,
  });

  final IconData icon;
  final IconData activeIcon;
  final String label;
  final int badge;
}

/// Floating evergreen pill navigation — the signature chrome of the shell.
class DockNav extends StatelessWidget {
  const DockNav({
    super.key,
    required this.index,
    required this.onSelect,
    this.unread = 0,
  });

  final int index;
  final ValueChanged<int> onSelect;
  final int unread;

  @override
  Widget build(BuildContext context) {
    final items = [
      DockItem(
        icon: AppIcons.myReports(),
        activeIcon: AppIcons.myReports(active: true),
        label: 'Reports',
      ),
      DockItem(
        icon: AppIcons.nearby(),
        activeIcon: AppIcons.nearby(active: true),
        label: 'Nearby',
      ),
      DockItem(icon: AppIcons.chat, activeIcon: AppIcons.chat, label: 'Chats'),
      DockItem(
        icon: AppIcons.notifications(),
        activeIcon: AppIcons.notifications(active: true),
        label: 'Alerts',
        badge: unread,
      ),
      DockItem(
        icon: AppIcons.user,
        activeIcon: AppIcons.user,
        label: 'Profile',
      ),
    ];

    // Use viewPadding (not padding) so Android gesture/3-button nav insets
    // are always applied even when ancestors already consumed SafeArea padding.
    final bottomInset = MediaQuery.viewPaddingOf(context).bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, bottomInset + 8),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: AppColors.inkSoft,
          borderRadius: BorderRadius.circular(AppRadius.pill),
          boxShadow: AppShadows.dock(),
        ),
        child: SizedBox(
          height: 64,
          child: Row(
            children: List.generate(items.length, (i) {
              final item = items[i];
              final selected = i == index;
              return Expanded(
                child: _DockSlot(
                  item: item,
                  selected: selected,
                  onTap: () {
                    HapticFeedback.selectionClick();
                    onSelect(i);
                  },
                ),
              );
            }),
          ),
        ),
      ),
    );
  }
}

class _DockSlot extends StatelessWidget {
  const _DockSlot({
    required this.item,
    required this.selected,
    required this.onTap,
  });

  final DockItem item;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: item.label,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: Center(
          child: AnimatedContainer(
            duration: AppMotion.fast,
            curve: Curves.easeOutCubic,
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: selected ? AppColors.brand : Colors.transparent,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: Badge(
              isLabelVisible: item.badge > 0,
              label: Text('${item.badge}'),
              backgroundColor: AppColors.danger,
              child: Icon(
                selected ? item.activeIcon : item.icon,
                size: 22,
                color: selected
                    ? Colors.white
                    : Colors.white.withValues(alpha: 0.52),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
