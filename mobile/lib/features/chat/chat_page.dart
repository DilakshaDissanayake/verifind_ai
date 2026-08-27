import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../core/api_client.dart';
import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/network_image_frame.dart';
import '../auth/auth_cubit.dart';

class ChatPage extends StatefulWidget {
  const ChatPage({
    super.key,
    required this.roomId,
    this.currentUserId,
    this.title,
  });
  final String roomId;
  final String? currentUserId;
  final String? title;

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final List<Map<String, dynamic>> _messages = [];
  bool _handoverDone = false;
  bool _handoverBusy = false;
  final _ctrl = TextEditingController();
  final _scroll = ScrollController();
  final _recorder = AudioRecorder();
  final _player = AudioPlayer();
  WebSocketChannel? _ws;
  StreamSubscription? _wsSub;
  bool _loading = true;
  bool _wsConnected = false;
  bool _recording = false;
  bool _uploading = false;
  String? _error;
  String? _viewerId;
  String _title = 'Claim chat';
  String? _playingId;

  @override
  void initState() {
    super.initState();
    final auth = context.read<AuthCubit>().state;
    if (auth is AuthAuthenticated) {
      _viewerId = widget.currentUserId ?? auth.userId;
    } else {
      _viewerId = widget.currentUserId;
    }
    if (widget.title != null && widget.title!.isNotEmpty) {
      _title = widget.title!;
    }
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await Future.wait([_loadRoom(), _loadHistory()]);
    _connectWs();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    _scroll.dispose();
    _wsSub?.cancel();
    _ws?.sink.close();
    _recorder.dispose();
    _player.dispose();
    super.dispose();
  }

  Future<void> _loadRoom() async {
    try {
      final api = context.read<ApiClient>();
      final room = await api.getChatRoom(widget.roomId);
      final title = room['title'] as String?;
      final viewer = room['viewer_id'] as String?;
      final active = room['is_active'] as bool? ?? true;
      if (!mounted) return;
      setState(() {
        if (title != null && title.isNotEmpty) _title = title;
        if (viewer != null && viewer.isNotEmpty) _viewerId = viewer;
        _handoverDone = !active;
      });
    } catch (_) {
      // title stays default
    }
  }

  Future<void> _completeHandover() async {
    if (_handoverBusy || _handoverDone) return;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Mark handover complete?'),
        content: const Text(
          'This hides both lost and found posts from public feeds. '
          'Admins can still export the handover report.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Complete'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    setState(() => _handoverBusy = true);
    try {
      final api = context.read<ApiClient>();
      final res = await api.completeHandover(widget.roomId);
      if (!mounted) return;
      setState(() {
        _handoverDone = true;
        _handoverBusy = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            (res['message'] as String?) ??
                'Handover complete — posts are now hidden.',
          ),
        ),
      );
      await _loadHistory();
    } catch (e) {
      if (!mounted) return;
      setState(() => _handoverBusy = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ApiClient.friendlyError(e))),
      );
    }
  }

  Future<void> _loadHistory() async {
    try {
      final api = context.read<ApiClient>();
      final data = await api.getChatMessages(widget.roomId);
      final msgs = List<Map<String, dynamic>>.from(
        (data['messages'] as List? ?? []).map(
          (e) => Map<String, dynamic>.from(e as Map),
        ),
      );
      final viewer = data['viewer_id'] as String?;
      final title = data['title'] as String?;
      if (!mounted) return;
      setState(() {
        _messages
          ..clear()
          ..addAll(msgs);
        if (viewer != null && viewer.isNotEmpty) _viewerId = viewer;
        if (title != null && title.isNotEmpty) _title = title;
        _loading = false;
      });
      _scrollBottom();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = ApiClient.friendlyError(e);
        _loading = false;
      });
    }
  }

  void _connectWs() {
    try {
      final api = context.read<ApiClient>();
      final uri = api.chatWebSocketUri(widget.roomId);
      _ws = WebSocketChannel.connect(uri);
      setState(() => _wsConnected = true);
      _wsSub = _ws!.stream.listen(
        (raw) {
          try {
            final msg = Map<String, dynamic>.from(
              json.decode(raw as String) as Map,
            );
            final mid = msg['message_id'] as String?;
            if (mid != null && _messages.any((m) => m['message_id'] == mid)) {
              return;
            }
            setState(() => _messages.add(msg));
            _scrollBottom();
          } catch (_) {}
        },
        onError: (_) => setState(() => _wsConnected = false),
        onDone: () => setState(() => _wsConnected = false),
      );
    } catch (_) {
      setState(() => _wsConnected = false);
    }
  }

  Future<void> _send() async {
    final body = _ctrl.text.trim();
    if (body.isEmpty || _uploading) return;
    _ctrl.clear();
    HapticFeedback.selectionClick();
    try {
      final api = context.read<ApiClient>();
      final sent = await api.sendChatMessage(widget.roomId, body);
      final mid = sent['message_id'] as String?;
      final already =
          mid != null && _messages.any((m) => m['message_id'] == mid);
      if (!already && mounted) {
        setState(() => _messages.add(Map<String, dynamic>.from(sent)));
        _scrollBottom();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(ApiClient.friendlyError(e))));
      }
    }
  }

  Future<void> _pickImage() async {
    if (_uploading) return;
    final picker = ImagePicker();
    final file = await picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 85,
    );
    if (file == null) return;
    await _uploadMedia(await file.readAsBytes(), file.name, 'image');
  }

  Future<void> _toggleRecord() async {
    if (_uploading) return;
    if (_recording) {
      final path = await _recorder.stop();
      setState(() => _recording = false);
      if (path == null) return;
      final bytes = await File(path).readAsBytes();
      final name = p.basename(path).endsWith('.m4a')
          ? p.basename(path)
          : 'voice.m4a';
      await _uploadMedia(bytes, name, 'voice');
      return;
    }
    final allowed = await _recorder.hasPermission();
    if (!allowed) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Microphone permission required')),
        );
      }
      return;
    }
    final dir = await getTemporaryDirectory();
    final path = p.join(
      dir.path,
      'vf_${DateTime.now().millisecondsSinceEpoch}.m4a',
    );
    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.aacLc),
      path: path,
    );
    HapticFeedback.mediumImpact();
    setState(() => _recording = true);
  }

  Future<void> _uploadMedia(
    List<int> bytes,
    String filename,
    String type,
  ) async {
    setState(() => _uploading = true);
    try {
      final api = context.read<ApiClient>();
      final sent = await api.sendChatMedia(
        roomId: widget.roomId,
        bytes: bytes,
        filename: filename,
        messageType: type,
      );
      final mid = sent['message_id'] as String?;
      final already =
          mid != null && _messages.any((m) => m['message_id'] == mid);
      if (!already && mounted) {
        setState(() => _messages.add(Map<String, dynamic>.from(sent)));
        _scrollBottom();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(ApiClient.friendlyError(e))));
      }
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<void> _playVoice(String messageId, String url) async {
    if (_playingId == messageId) {
      await _player.stop();
      setState(() => _playingId = null);
      return;
    }
    await _player.stop();
    setState(() => _playingId = messageId);
    await _player.play(UrlSource(url));
    _player.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _playingId = null);
    });
  }

  void _scrollBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOut,
        );
      }
    });
  }

  bool _isMe(Map<String, dynamic> msg) {
    if (msg['is_mine'] == true) return true;
    final type = (msg['message_type'] as String? ?? 'text').toLowerCase();
    if (type == 'system') return false;
    final sid = msg['sender_id'] as String? ?? '';
    return _viewerId != null && sid == _viewerId;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Icon(AppIcons.shieldCheck, size: 16, color: statusColors.success),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    _title,
                    style: theme.textTheme.titleMedium,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  Text(
                    _handoverDone
                        ? 'Handover complete · posts hidden'
                        : 'PASS verified · anonymous',
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          if (!_handoverDone)
            TextButton(
              onPressed: _handoverBusy ? null : _completeHandover,
              child: _handoverBusy
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Done'),
            ),
          Padding(
            padding: const EdgeInsets.only(right: AppSpacing.md),
            child: Tooltip(
              message: _wsConnected ? 'Live' : 'Reconnecting…',
              child: Icon(
                _wsConnected ? AppIcons.wifiOn : AppIcons.wifiOff,
                size: 18,
                color: _wsConnected
                    ? statusColors.success
                    : statusColors.warning,
              ),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_error != null)
            Container(
              width: double.infinity,
              color: statusColors.danger.withValues(alpha: 0.12),
              padding: const EdgeInsets.all(AppSpacing.sm),
              child: Text(
                _error!,
                style: TextStyle(color: statusColors.danger),
              ),
            ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                ? EmptyState(
                    icon: AppIcons.chat,
                    title: 'No messages yet',
                    message: 'Say hello and coordinate a safe handover.',
                  )
                : ListView.builder(
                    controller: _scroll,
                    padding: EdgeInsets.fromLTRB(
                      AppSpacing.md,
                      AppSpacing.md,
                      AppSpacing.md,
                      AppSpacing.xl + MediaQuery.of(context).padding.bottom,
                    ),
                    itemCount: _messages.length,
                    itemBuilder: (context, i) {
                      final msg = _messages[i];
                      final type = (msg['message_type'] as String? ?? 'text')
                          .toLowerCase();
                      if (type == 'system') {
                        return _SystemCard(msg: msg)
                            .animate()
                            .fadeIn(duration: 240.ms)
                            .slideY(begin: 0.08, end: 0);
                      }
                      return _MessageBubble(
                            msg: msg,
                            isMe: _isMe(msg),
                            playing:
                                _playingId == (msg['message_id'] as String?),
                            onPlayVoice: (url) => _playVoice(
                              msg['message_id'] as String? ?? '',
                              url,
                            ),
                          )
                          .animate()
                          .fadeIn(duration: 200.ms)
                          .slideY(begin: 0.12, end: 0);
                    },
                  ),
          ),
          if (_recording)
            Container(
              width: double.infinity,
              color: statusColors.danger.withValues(alpha: 0.1),
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(AppIcons.mic, size: 14, color: statusColors.danger),
                  const SizedBox(width: 6),
                  Text(
                    'Recording… tap mic to send',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: statusColors.danger,
                    ),
                  ),
                ],
              ),
            ),
          const Divider(height: 1),
          if (_handoverDone)
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Text(
                  'Handover complete. Both posts are hidden from public feeds.',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodySmall,
                ),
              ),
            )
          else
          SafeArea(
            top: false,
            child: Padding(
              padding: EdgeInsets.only(
                left: AppSpacing.sm,
                right: AppSpacing.sm,
                top: AppSpacing.sm,
                // SafeArea already applies viewPadding.bottom; only add keyboard + gap.
                bottom: MediaQuery.viewInsetsOf(context).bottom + AppSpacing.sm,
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  IconButton(
                    onPressed: _uploading ? null : _pickImage,
                    icon: Icon(AppIcons.image, size: 22),
                    tooltip: 'Send photo',
                  ),
                  IconButton(
                    onPressed: _uploading ? null : _toggleRecord,
                    icon: Icon(
                      _recording ? AppIcons.stop : AppIcons.mic,
                      size: 22,
                      color: _recording ? statusColors.danger : null,
                    ),
                    tooltip: _recording ? 'Stop & send' : 'Voice note',
                  ),
                  Expanded(
                    child: TextField(
                      controller: _ctrl,
                      enabled: !_uploading,
                      decoration: InputDecoration(
                        hintText: 'Type a message…',
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.lg,
                          vertical: AppSpacing.sm,
                        ),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                          borderSide: BorderSide.none,
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                          borderSide: BorderSide.none,
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                          borderSide: BorderSide(
                            color: theme.colorScheme.primary,
                            width: 1.4,
                          ),
                        ),
                      ),
                      onSubmitted: (_) => _send(),
                      textInputAction: TextInputAction.send,
                      maxLines: 4,
                      minLines: 1,
                    ),
                  ),
                  const SizedBox(width: 4),
                  if (_uploading)
                    const Padding(
                      padding: EdgeInsets.all(12),
                      child: SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    )
                  else
                    IconButton.filled(
                      onPressed: _send,
                      style: IconButton.styleFrom(
                        backgroundColor: AppColors.ink,
                        foregroundColor: Colors.white,
                        disabledBackgroundColor: AppColors.ink.withValues(
                          alpha: 0.4,
                        ),
                        disabledForegroundColor: Colors.white70,
                      ),
                      icon: const Icon(
                        AppIcons.send,
                        size: 20,
                        color: Colors.white,
                      ),
                      tooltip: 'Send',
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SystemCard extends StatelessWidget {
  const _SystemCard({required this.msg});
  final Map<String, dynamic> msg;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    final body = msg['body'] as String? ?? '';

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: statusColors.info.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(AppRadius.lg),
          border: Border.all(color: statusColors.info.withValues(alpha: 0.28)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(AppIcons.sparkle, size: 16, color: statusColors.info),
                const SizedBox(width: 6),
                Text(
                  'Match analysis',
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: statusColors.info,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              body.replaceFirst(RegExp(r'^Match analysis\n?'), ''),
              style: theme.textTheme.bodyMedium?.copyWith(height: 1.45),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({
    required this.msg,
    required this.isMe,
    required this.playing,
    required this.onPlayVoice,
  });
  final Map<String, dynamic> msg;
  final bool isMe;
  final bool playing;
  final void Function(String url) onPlayVoice;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final body = msg['body'] as String? ?? '';
    final type = (msg['message_type'] as String? ?? 'text').toLowerCase();
    final mediaUrl = msg['media_url'] as String?;
    final created = msg['created_at'] as String?;

    return Align(
      alignment: isMe ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        child: Column(
          crossAxisAlignment: isMe
              ? CrossAxisAlignment.end
              : CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(left: 4, right: 4, bottom: 4),
              child: Text(
                isMe ? 'You' : 'Them',
                style: theme.textTheme.labelSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                  color: cs.onSurface.withValues(alpha: 0.45),
                ),
              ),
            ),
            Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: EdgeInsets.symmetric(
                horizontal: type == 'image' ? 6 : 14,
                vertical: type == 'image' ? 6 : 10,
              ),
              decoration: BoxDecoration(
                color: isMe ? AppColors.brand : const Color(0xFFF1F5F9),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(22),
                  topRight: const Radius.circular(22),
                  bottomLeft: Radius.circular(isMe ? 22 : 6),
                  bottomRight: Radius.circular(isMe ? 6 : 22),
                ),
                border: isMe
                    ? null
                    : Border.all(color: AppColors.lightBorder, width: 1),
                boxShadow: isMe ? null : AppShadows.soft(),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (type == 'image' && mediaUrl != null) ...[
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: NetworkImageFrame(
                        url: mediaUrl,
                        width: 220,
                        height: 180,
                        fit: BoxFit.cover,
                      ),
                    ),
                    if (body.isNotEmpty && body != '[image]') ...[
                      const SizedBox(height: 6),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 6),
                        child: Text(
                          body,
                          style: TextStyle(
                            color: isMe ? Colors.white : AppColors.ink,
                          ),
                        ),
                      ),
                    ],
                  ] else if (type == 'voice' && mediaUrl != null) ...[
                    InkWell(
                      onTap: () => onPlayVoice(mediaUrl),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            playing ? AppIcons.stop : AppIcons.play,
                            size: 20,
                            color: isMe ? Colors.white : AppColors.ink,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            playing ? 'Playing…' : 'Voice note',
                            style: TextStyle(
                              color: isMe ? Colors.white : AppColors.ink,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ] else
                    Text(
                      body,
                      style: TextStyle(
                        color: isMe ? Colors.white : AppColors.ink,
                        height: 1.4,
                      ),
                    ),
                  if (created != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      _fmtTime(created),
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: isMe
                            ? Colors.white.withValues(alpha: 0.65)
                            : AppColors.lightInkMuted,
                        fontSize: 10,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _fmtTime(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      final h = dt.hour.toString().padLeft(2, '0');
      final m = dt.minute.toString().padLeft(2, '0');
      return '$h:$m';
    } catch (_) {
      return '';
    }
  }
}
