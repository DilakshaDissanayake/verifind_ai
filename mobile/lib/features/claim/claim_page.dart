import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../core/api_client.dart';
import '../../design/app_colors.dart';
import '../../design/app_icons.dart';
import '../../design/app_spacing.dart';
import '../../widgets/confidence_meter.dart';
import '../../widgets/step_timeline.dart';
import '../chat/chat_page.dart';
import '../auth/auth_cubit.dart';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

abstract class ClaimState extends Equatable {
  @override
  List<Object?> get props => [];
}

class ClaimInitial extends ClaimState {}

class ClaimLoading extends ClaimState {}

class ClaimQuestionsLoaded extends ClaimState {
  ClaimQuestionsLoaded({
    required this.questions,
    required this.sessionId,
    required this.attemptId,
  });
  final List<Map<String, dynamic>> questions;
  final String sessionId;
  final String attemptId;
  @override
  List<Object?> get props => [questions, sessionId, attemptId];
}

class ClaimResult extends ClaimState {
  ClaimResult({
    required this.decision,
    required this.score,
    this.chatRoomId,
    required this.message,
    this.claimAttemptId,
    this.matchId,
  });
  final String decision;
  final double score;
  final String? chatRoomId;
  final String message;
  final String? claimAttemptId;
  final String? matchId;
  @override
  List<Object?> get props => [decision, score, chatRoomId, claimAttemptId];
}

class ClaimError extends ClaimState {
  ClaimError(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}

// ---------------------------------------------------------------------------
// Cubit
// ---------------------------------------------------------------------------

class ClaimCubit extends Cubit<ClaimState> {
  ClaimCubit(this._api) : super(ClaimInitial());
  final ApiClient _api;

  Future<void> startClaim({
    required String matchId,
    required String foundReportId,
  }) async {
    emit(ClaimLoading());
    try {
      final data = await _api.startClaim(
        matchId: matchId,
        foundReportId: foundReportId,
      );
      if (data['allowed'] == false) {
        emit(ClaimError('This claim cannot be started.'));
        return;
      }
      final qs = List<Map<String, dynamic>>.from(
        (data['questions'] as List? ?? []).map(
          (e) => Map<String, dynamic>.from(e as Map),
        ),
      );
      emit(
        ClaimQuestionsLoaded(
          questions: qs,
          sessionId: data['verification_session_id'] as String? ?? '',
          attemptId: data['claim_attempt_id'] as String? ?? '',
        ),
      );
    } catch (e) {
      emit(ClaimError(ApiClient.friendlyError(e)));
    }
  }

  Future<void> submitAnswers({
    required String sessionId,
    required String attemptId,
    required List<String> answers,
  }) async {
    emit(ClaimLoading());
    try {
      final data = await _api.submitAnswers(
        verificationSessionId: sessionId,
        claimAttemptId: attemptId,
        answers: answers,
      );
      emit(
        ClaimResult(
          decision: data['decision'] as String? ?? 'BLOCK',
          score: ((data['overall_score'] as num?)?.toDouble() ?? 0.0),
          chatRoomId: data['chat_room_id'] as String?,
          message: data['message'] as String? ?? '',
          claimAttemptId: data['claim_attempt_id'] as String? ?? attemptId,
          matchId: data['match_id'] as String?,
        ),
      );
    } catch (e) {
      emit(ClaimError(ApiClient.friendlyError(e)));
    }
  }
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

class ClaimPage extends StatelessWidget {
  const ClaimPage({
    super.key,
    required this.matchId,
    required this.foundReportId,
    this.title,
  });
  final String matchId;
  final String foundReportId;
  final String? title;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (ctx) =>
          ClaimCubit(ctx.read<ApiClient>())
            ..startClaim(matchId: matchId, foundReportId: foundReportId),
      child: _ClaimView(title: title),
    );
  }
}

class _ClaimView extends StatelessWidget {
  const _ClaimView({this.title});
  final String? title;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title ?? 'Verify Ownership')),
      body: BlocBuilder<ClaimCubit, ClaimState>(
        builder: (context, state) {
          if (state is ClaimLoading || state is ClaimInitial) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  PulsingIcon(
                    icon: AppIcons.fingerprint,
                    color: Theme.of(context).colorScheme.primary,
                    size: 40,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  Text(
                    'Generating questions from the vault\u2026',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ],
              ),
            );
          }
          if (state is ClaimError) {
            final statusColors = Theme.of(
              context,
            ).extension<AppStatusColors>()!;
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.xxl),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      AppIcons.xCircle,
                      size: 56,
                      color: statusColors.danger,
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    Text(
                      state.message,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
              ),
            );
          }
          if (state is ClaimQuestionsLoaded) {
            return _QuestionsForm(state: state);
          }
          if (state is ClaimResult) {
            return _ResultView(result: state);
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}

class _QuestionsForm extends StatefulWidget {
  const _QuestionsForm({required this.state});
  final ClaimQuestionsLoaded state;
  @override
  State<_QuestionsForm> createState() => _QuestionsFormState();
}

class _QuestionsFormState extends State<_QuestionsForm> {
  late final List<TextEditingController> _controllers;
  final _formKey = GlobalKey<FormState>();

  @override
  void initState() {
    super.initState();
    _controllers = List.generate(
      widget.state.questions.length,
      (_) => TextEditingController()..addListener(() => setState(() {})),
    );
  }

  @override
  void dispose() {
    for (final c in _controllers) {
      c.dispose();
    }
    super.dispose();
  }

  int get _answeredCount =>
      _controllers.where((c) => c.text.trim().isNotEmpty).length;

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    final answers = _controllers.map((c) => c.text.trim()).toList();
    context.read<ClaimCubit>().submitAnswers(
      sessionId: widget.state.sessionId,
      attemptId: widget.state.attemptId,
      answers: answers,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final total = widget.state.questions.length;

    return Form(
      key: _formKey,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.lg,
              AppSpacing.lg,
              AppSpacing.lg,
              0,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      AppIcons.shieldCheck,
                      color: theme.colorScheme.primary,
                      size: 20,
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Text(
                        'Answer these questions to prove ownership.',
                        style: theme.textTheme.titleSmall,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Only the true owner can answer correctly \u2014 these are based on details hidden from the public.',
                  style: theme.textTheme.bodySmall,
                ),
                const SizedBox(height: AppSpacing.lg),
                ClipRRect(
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                  child: LinearProgressIndicator(
                    value: total == 0 ? 0 : _answeredCount / total,
                    minHeight: 6,
                    backgroundColor: theme.colorScheme.surfaceContainerHighest,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  '$_answeredCount of $total answered',
                  style: theme.textTheme.bodySmall,
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(AppSpacing.lg),
              children: [
                ...widget.state.questions.asMap().entries.map((entry) {
                  final i = entry.key;
                  final q = entry.value;
                  return Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.xl),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              width: 22,
                              height: 22,
                              margin: const EdgeInsets.only(top: 2),
                              decoration: BoxDecoration(
                                color: theme.colorScheme.primary.withValues(
                                  alpha: 0.14,
                                ),
                                shape: BoxShape.circle,
                              ),
                              alignment: Alignment.center,
                              child: Text(
                                '${i + 1}',
                                style: theme.textTheme.labelSmall?.copyWith(
                                  color: theme.colorScheme.primary,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ),
                            const SizedBox(width: AppSpacing.sm),
                            Expanded(
                              child: Text(
                                q['question'] as String? ?? '',
                                style: theme.textTheme.bodyLarge?.copyWith(
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: AppSpacing.sm),
                        TextFormField(
                          controller: _controllers[i],
                          decoration: const InputDecoration(
                            hintText: 'Your answer\u2026',
                          ),
                          validator: (v) => (v == null || v.trim().isEmpty)
                              ? 'Required'
                              : null,
                          maxLines: 2,
                        ),
                      ],
                    ),
                  );
                }),
              ],
            ),
          ),
          SafeArea(
            minimum: const EdgeInsets.fromLTRB(
              AppSpacing.lg,
              0,
              AppSpacing.lg,
              AppSpacing.lg,
            ),
            child: FilledButton.icon(
              onPressed: _submit,
              icon: Icon(AppIcons.shieldCheck, size: 18),
              label: const Text('Submit Answers'),
            ),
          ),
        ],
      ),
    );
  }
}

class _ResultView extends StatefulWidget {
  const _ResultView({required this.result});
  final ClaimResult result;

  @override
  State<_ResultView> createState() => _ResultViewState();
}

class _ResultViewState extends State<_ResultView> {
  Timer? _poll;
  String? _chatRoomId;
  String _decision = '';
  String _message = '';
  bool _polling = false;

  @override
  void initState() {
    super.initState();
    _chatRoomId = widget.result.chatRoomId;
    _decision = widget.result.decision;
    _message = widget.result.message;
    if (_decision == 'REVIEW' && _chatRoomId == null) {
      _startPoll();
    }
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  void _startPoll() {
    _polling = true;
    _poll = Timer.periodic(const Duration(seconds: 4), (_) => _checkStatus());
    _checkStatus();
  }

  Future<void> _checkStatus() async {
    final attemptId = widget.result.claimAttemptId;
    if (attemptId == null || attemptId.isEmpty) return;
    try {
      final api = context.read<ApiClient>();
      final data = await api.getClaimStatus(attemptId);
      final status = data['status'] as String? ?? '';
      final roomId = data['chat_room_id'] as String?;
      final decision = data['decision'] as String?;

      if (!mounted) return;

      if (status == 'passed' || decision == 'PASS') {
        _poll?.cancel();
        setState(() {
          _decision = 'PASS';
          _chatRoomId = roomId;
          _polling = false;
          _message = roomId != null
              ? 'Admin approved — chat room is now open.'
              : 'Admin approved. Waiting for chat room\u2026';
        });
        // If room id still missing, try by-match once
        if (_chatRoomId == null && widget.result.matchId != null) {
          try {
            final room = await api.getChatRoomByMatch(widget.result.matchId!);
            if (mounted) {
              setState(() => _chatRoomId = room['room_id'] as String?);
            }
          } catch (_) {}
        }
      } else if (status == 'blocked' || decision == 'BLOCK') {
        _poll?.cancel();
        setState(() {
          _decision = 'BLOCK';
          _polling = false;
          _message = 'Admin blocked this claim.';
        });
      }
    } catch (_) {
      // keep polling
    }
  }

  void _openChat() {
    final roomId = _chatRoomId;
    if (roomId == null) return;
    final auth = context.read<AuthCubit>().state;
    final uid = auth is AuthAuthenticated ? auth.userId : null;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => RepositoryProvider.value(
          value: context.read<ApiClient>(),
          child: ChatPage(roomId: roomId, currentUserId: uid),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = theme.extension<AppStatusColors>()!;
    final pass = _decision == 'PASS';
    final review = _decision == 'REVIEW';
    final color = pass
        ? statusColors.success
        : review
        ? statusColors.warning
        : statusColors.danger;
    final icon = pass
        ? AppIcons.checkCircle
        : review
        ? AppIcons.clock
        : AppIcons.xCircle;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
                  width: 108,
                  height: 108,
                  decoration: BoxDecoration(
                    color: pass
                        ? AppColors.brand
                        : color.withValues(alpha: 0.16),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    icon,
                    color: pass ? AppColors.ink : color,
                    size: 52,
                  ),
                )
                .animate()
                .scale(
                  duration: 420.ms,
                  curve: Curves.elasticOut,
                  begin: const Offset(0.4, 0.4),
                )
                .fadeIn(duration: 220.ms),
            const SizedBox(height: AppSpacing.xl),
            Text(
              _decision,
              style: theme.textTheme.headlineSmall?.copyWith(color: color),
            ).animate().fadeIn(delay: 150.ms),
            const SizedBox(height: AppSpacing.lg),
            SizedBox(
              width: 220,
              child: ConfidenceMeter(
                value: widget.result.score,
                label: 'Ownership confidence',
                color: color,
              ),
            ).animate().fadeIn(delay: 220.ms),
            const SizedBox(height: AppSpacing.lg),
            Text(
              _message,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.65),
              ),
            ),
            if (_polling) ...[
              const SizedBox(height: AppSpacing.lg),
              Text(
                'Waiting for admin approval\u2026',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: statusColors.warning,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              const SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ],
            if (pass && _chatRoomId != null) ...[
              const SizedBox(height: AppSpacing.xxl),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: null,
                      icon: Icon(
                        AppIcons.checkCircle,
                        size: 18,
                        color: statusColors.success,
                      ),
                      label: Text(
                        'Pass',
                        style: TextStyle(
                          color: statusColors.success,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      style: OutlinedButton.styleFrom(
                        side: BorderSide(
                          color: statusColors.success.withValues(alpha: 0.55),
                        ),
                        disabledForegroundColor: statusColors.success,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: _openChat,
                      icon: Icon(AppIcons.chat, size: 18),
                      label: const Text('Chat'),
                    ),
                  ),
                ],
              ).animate().fadeIn(delay: 280.ms),
            ],
          ],
        ),
      ),
    );
  }
}
