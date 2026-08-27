import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/api_client.dart';
import '../../core/location_service.dart';
import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';
import '../auth/account_status_cubit.dart';
import '../auth/auth_cubit.dart';
import 'ai_status_page.dart';

class _PickedImage {
  _PickedImage({required this.bytes, required this.name});
  final Uint8List bytes;
  final String name;
}

class CreateReportPage extends StatefulWidget {
  const CreateReportPage({
    super.key,
    this.initialType = 'LOST',
    this.matchedToReportId,
    this.matchedTitle,
  });

  final String initialType;
  final String? matchedToReportId;
  final String? matchedTitle;

  @override
  State<CreateReportPage> createState() => _CreateReportPageState();
}

class _CreateReportPageState extends State<CreateReportPage> {
  static const int _maxImages = 5;
  static const List<String> _categoryOptions = [
    'electronics',
    'bag',
    'wallet',
    'keys',
    'clothing',
    'jewelry',
    'document',
    'other',
  ];

  late String _type;
  final _manualCategory = TextEditingController();
  final Set<String> _selectedCategories = {};
  final _title = TextEditingController();
  final _description = TextEditingController();
  bool _submitting = false;
  String? _submitStep;
  String? _errorMessage;
  bool _isStrikeWarning = false;
  String? _locationHint;
  final List<_PickedImage> _images = [];
  final _location = LocationService();
  final _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
    _type = widget.initialType;
    if (widget.matchedTitle != null && widget.matchedTitle!.isNotEmpty) {
      _title.text = 'Found: ${widget.matchedTitle}';
    }
  }

  @override
  void dispose() {
    _manualCategory.dispose();
    _title.dispose();
    _description.dispose();
    super.dispose();
  }

  Future<void> _pickImages() async {
    final remaining = _maxImages - _images.length;
    if (remaining <= 0) return;
    HapticFeedback.lightImpact();
    final files = await _picker.pickMultiImage(
      imageQuality: 85,
      limit: remaining,
    );
    if (files.isEmpty) return;
    final added = <_PickedImage>[];
    for (final file in files.take(remaining)) {
      final bytes = await file.readAsBytes();
      added.add(_PickedImage(bytes: bytes, name: file.name));
    }
    setState(() => _images.addAll(added));
  }

  void _removeImage(int index) {
    HapticFeedback.selectionClick();
    setState(() => _images.removeAt(index));
  }

  void _toggleCategory(String category) {
    setState(() {
      if (!_selectedCategories.add(category)) {
        _selectedCategories.remove(category);
      }
    });
  }

  Future<void> _submit() async {
    if (!_hasRequiredFields) {
      setState(() {
        _errorMessage = 'Please complete category, title, and description.';
        _isStrikeWarning = false;
      });
      return;
    }
    final api = context.read<ApiClient>();
    setState(() {
      _submitting = true;
      _errorMessage = null;
      _isStrikeWarning = false;
      _submitStep = 'Getting your location\u2026';
    });
    try {
      final loc = await _location.currentFuzzed();
      setState(() {
        _locationHint = 'GPS locked \u00b7 privacy fuzz \u00b1500 m applied';
        _submitStep = 'Submitting report\u2026';
      });
      final body = <String, dynamic>{
        'report_type': _type,
        'category': _selectedCategories.join(', '),
        'title': _title.text.trim(),
        'description': _description.text.trim(),
        'latitude': loc.lat,
        'longitude': loc.lon,
        'location_label': 'Device GPS (fuzzed +-500m)',
        'client_fuzzed': true,
        if (widget.matchedToReportId != null)
          'matched_to_report_id': widget.matchedToReportId,
      };
      final res = await api.createReport(body);
      final reportId = res['report_id'] as String?;
      if (reportId != null && _images.isNotEmpty) {
        for (var i = 0; i < _images.length; i++) {
          setState(
            () => _submitStep =
                'Uploading photo ${i + 1}/${_images.length}\u2026',
          );
          final img = _images[i];
          await api.uploadReportImage(
            reportId: reportId,
            bytes: img.bytes,
            filename: img.name,
            isPrimary: i == 0,
          );
        }
      }
      if (reportId != null && mounted) {
        HapticFeedback.mediumImpact();
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (_) => RepositoryProvider.value(
              value: api,
              child: AIStatusPage(reportId: reportId, reportTitle: _title.text),
            ),
          ),
        );
        return;
      }
      setState(() => _errorMessage = 'Report accepted but no ID was returned.');
    } catch (e) {
      final msg = ApiClient.friendlyError(e);
      final lower = msg.toLowerCase();
      final strike = lower.contains('warning') ||
          lower.contains('prohibited') ||
          lower.contains('strike') ||
          lower.contains('blocked') ||
          lower.contains('3 attempts');
      if (!mounted) return;
      setState(() {
        _errorMessage = msg;
        _isStrikeWarning = strike;
      });
      if (strike) {
        HapticFeedback.heavyImpact();
        if (lower.contains('blocked')) {
          try {
            context.read<AccountStatusCubit>().markBlocked();
          } catch (_) {
            // Cubit not in tree when opened outside home shell.
          }
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: Theme.of(context)
                .extension<AppStatusColors>()!
                .danger,
            content: Text(
              msg,
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
            ),
            duration: const Duration(seconds: 6),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
          _submitStep = null;
        });
      }
    }
  }

    bool get _hasRequiredFields =>
      _selectedCategories.isNotEmpty &&
      _title.text.trim().isNotEmpty &&
      _description.text.trim().isNotEmpty;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    final linked = widget.matchedToReportId != null;
    final canSubmit = _hasRequiredFields;

    return Scaffold(
      appBar: AppBar(
        title: Text(linked ? 'Report as Found' : 'Create Report'),
        actions: [
          IconButton(
            tooltip: 'Logout',
            onPressed: () => context.read<AuthCubit>().logout(),
            icon: Icon(AppIcons.signOut),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          AppSpacing.lg,
          AppSpacing.lg,
          AppSpacing.xxxl,
        ),
        children: [
          if (linked) ...[
            Container(
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: AppColors.brandSoft,
                borderRadius: BorderRadius.circular(AppRadius.lg),
              ),
              child: Row(
                children: [
                  Icon(AppIcons.link, color: AppColors.ink),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Linked to a LOST post',
                          style: theme.textTheme.titleSmall,
                        ),
                        Text(
                          widget.matchedTitle ?? widget.matchedToReportId!,
                          style: theme.textTheme.bodySmall,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
          ],
          Row(
            children: [
              Expanded(
                child: _TypeTile(
                  label: 'LOST',
                  icon: AppIcons.lost,
                  color: statusColors.lost,
                  selected: _type == 'LOST',
                  onTap: linked ? null : () => setState(() => _type = 'LOST'),
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: _TypeTile(
                  label: 'FOUND',
                  icon: AppIcons.found,
                  color: statusColors.found,
                  selected: _type == 'FOUND',
                  onTap: linked ? null : () => setState(() => _type = 'FOUND'),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(
            'Categories *',
            style: theme.textTheme.titleSmall,
          ),
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: _categoryOptions.map((category) {
              final selected = _selectedCategories.contains(category);
              return FilterChip(
                label: Text(category[0].toUpperCase() + category.substring(1)),
                selected: selected,
                onSelected: _submitting
                    ? null
                    : (_) => _toggleCategory(category),
              );
            }).toList(),
          ),
          const SizedBox(height: AppSpacing.sm),
          TextField(
            controller: _manualCategory,
            decoration: InputDecoration(
              labelText: 'Specific item or manual category',
              hintText: 'Example: Dell laptop bag',
              prefixIcon: Icon(AppIcons.tag, size: 20),
            ),
            onChanged: (value) {
              final manual = value.trim().toLowerCase();
              setState(() {
                _selectedCategories.removeWhere(
                  (category) => !_categoryOptions.contains(category),
                );
                if (manual.isNotEmpty) {
                  _selectedCategories.add(manual);
                }
              });
            },
          ),
          const SizedBox(height: AppSpacing.md),
          TextField(
            controller: _title,
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(
              labelText: 'Title *',
              prefixIcon: Icon(AppIcons.sparkle, size: 20),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          TextField(
            controller: _description,
            onChanged: (_) => setState(() {}),
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Description *',
              alignLabelWithHint: true,
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          Text('Photos', style: theme.textTheme.titleSmall),
          const SizedBox(height: AppSpacing.sm),
          _PhotoGrid(
            images: _images,
            maxImages: _maxImages,
            onAdd: _submitting ? null : _pickImages,
            onRemove: _submitting ? null : _removeImage,
          ),
          if (_locationHint != null) ...[
            const SizedBox(height: AppSpacing.md),
            Row(
              children: [
                Icon(AppIcons.gps, size: 14, color: statusColors.success),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(_locationHint!, style: theme.textTheme.bodySmall),
                ),
              ],
            ),
          ],
          if (_errorMessage != null) ...[
            const SizedBox(height: AppSpacing.md),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: statusColors.danger.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(AppRadius.md),
                border: Border.all(
                  color: statusColors.danger.withValues(alpha: 0.55),
                  width: 1.4,
                ),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    AppIcons.warningCircle,
                    color: statusColors.danger,
                    size: 22,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (_isStrikeWarning)
                          Text(
                            _errorMessage!.toLowerCase().contains('blocked')
                                ? 'Account blocked'
                                : 'Content warning',
                            style: TextStyle(
                              color: statusColors.danger,
                              fontWeight: FontWeight.w800,
                              fontSize: 14,
                            ),
                          ),
                        if (_isStrikeWarning) const SizedBox(height: 4),
                        Text(
                          _errorMessage!,
                          style: TextStyle(
                            color: statusColors.danger,
                            fontSize: 13,
                            fontWeight: _isStrikeWarning
                                ? FontWeight.w600
                                : FontWeight.w500,
                            height: 1.35,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          AppSpacing.sm,
          AppSpacing.lg,
          AppSpacing.lg,
        ),
        child: FilledButton(
          onPressed: (_submitting || !canSubmit) ? null : _submit,
          child: _submitting
              ? Row(
                  mainAxisSize: MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.2,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Text(_submitStep ?? 'Submitting\u2026'),
                  ],
                )
              : Text(linked ? 'Submit FOUND + match' : 'Submit report'),
        ),
      ),
    );
  }
}

class _TypeTile extends StatelessWidget {
  const _TypeTile({
    required this.label,
    required this.icon,
    required this.color,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final Color color;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap == null
          ? null
          : () {
              HapticFeedback.selectionClick();
              onTap!();
            },
      borderRadius: BorderRadius.circular(AppRadius.md),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.lg),
        decoration: BoxDecoration(
          color: selected ? color : Colors.white,
          borderRadius: BorderRadius.circular(AppRadius.lg),
          boxShadow: AppShadows.soft(),
        ),
        child: Column(
          children: [
            Icon(
              icon,
              color: selected
                  ? AppColors.ink
                  : theme.colorScheme.onSurface.withValues(alpha: 0.45),
            ),
            const SizedBox(height: 6),
            Text(
              label,
              style: theme.textTheme.labelLarge?.copyWith(
                color: selected
                    ? AppColors.ink
                    : theme.colorScheme.onSurface.withValues(alpha: 0.55),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PhotoGrid extends StatelessWidget {
  const _PhotoGrid({
    required this.images,
    required this.maxImages,
    required this.onAdd,
    required this.onRemove,
  });

  final List<_PickedImage> images;
  final int maxImages;
  final VoidCallback? onAdd;
  final void Function(int index)? onRemove;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox(
      height: 92,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: images.length + (images.length < maxImages ? 1 : 0),
        separatorBuilder: (_, __) => const SizedBox(width: AppSpacing.sm),
        itemBuilder: (context, index) {
          if (index == images.length) {
            return InkWell(
              onTap: onAdd,
              borderRadius: BorderRadius.circular(AppRadius.md),
              child: DottedBox(
                width: 92,
                height: 92,
                color: theme.colorScheme.outline,
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(AppIcons.addReport, color: theme.colorScheme.primary),
                    const SizedBox(height: 4),
                    Text(
                      '${images.length}/$maxImages',
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            );
          }
          final img = images[index];
          return Stack(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(AppRadius.md),
                child: Image.memory(
                  img.bytes,
                  width: 92,
                  height: 92,
                  fit: BoxFit.cover,
                ),
              ),
              if (index == 0)
                Positioned(
                  left: 4,
                  bottom: 4,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.black54,
                      borderRadius: BorderRadius.circular(AppRadius.sm),
                    ),
                    child: const Text(
                      'Primary',
                      style: TextStyle(color: Colors.white, fontSize: 10),
                    ),
                  ),
                ),
              Positioned(
                top: 2,
                right: 2,
                child: GestureDetector(
                  onTap: onRemove == null ? null : () => onRemove!(index),
                  child: Container(
                    padding: const EdgeInsets.all(2),
                    decoration: const BoxDecoration(
                      color: Colors.black87,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.close,
                      color: Colors.white,
                      size: 14,
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

/// Simple dashed-border container (no extra dependency) for the "add photo" tile.
class DottedBox extends StatelessWidget {
  const DottedBox({
    super.key,
    required this.width,
    required this.height,
    required this.color,
    required this.child,
  });

  final double width;
  final double height;
  final Color color;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _DashedBorderPainter(color: color, radius: AppRadius.md),
      child: SizedBox(width: width, height: height, child: child),
    );
  }
}

class _DashedBorderPainter extends CustomPainter {
  _DashedBorderPainter({required this.color, required this.radius});
  final Color color;
  final double radius;

  @override
  void paint(Canvas canvas, Size size) {
    final rrect = RRect.fromRectAndRadius(
      Offset.zero & size,
      Radius.circular(radius),
    );
    final path = Path()..addRRect(rrect);
    final dashPath = Path();
    for (final metric in path.computeMetrics()) {
      double distance = 0;
      const dashWidth = 5.0;
      const dashGap = 4.0;
      while (distance < metric.length) {
        dashPath.addPath(
          metric.extractPath(distance, distance + dashWidth),
          Offset.zero,
        );
        distance += dashWidth + dashGap;
      }
    }
    canvas.drawPath(
      dashPath,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.4,
    );
  }

  @override
  bool shouldRepaint(covariant _DashedBorderPainter oldDelegate) =>
      oldDelegate.color != color || oldDelegate.radius != radius;
}
