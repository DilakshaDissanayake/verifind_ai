import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:verifind_mobile/core/api_client.dart';

abstract class AuthState extends Equatable {
  @override
  List<Object?> get props => [];
}

class AuthInitial extends AuthState {}

class AuthLoading extends AuthState {}

class AuthAuthenticated extends AuthState {
  AuthAuthenticated({
    required this.userId,
    required this.email,
    required this.token,
  });
  final String userId;
  final String email;
  final String token;
  @override
  List<Object?> get props => [userId, email, token];
}

class AuthNeedsConfirmation extends AuthState {
  AuthNeedsConfirmation(this.email, this.message);
  final String email;
  final String message;
  @override
  List<Object?> get props => [email, message];
}

class AuthError extends AuthState {
  AuthError(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}

class AuthCubit extends Cubit<AuthState> {
  AuthCubit(this._api) : super(AuthInitial());
  final ApiClient _api;

  Future<void> login(String email, String password) async {
    emit(AuthLoading());
    try {
      final data = await _api.login(email, password);
      final token = data['access_token'] as String;
      _api.setToken(token);
      emit(
        AuthAuthenticated(
          userId: data['user_id'] as String,
          email: data['email'] as String? ?? email,
          token: token,
        ),
      );
    } catch (e) {
      emit(AuthError(_friendly(e)));
    }
  }

  Future<void> register(
    String email,
    String password, {
    String? displayName,
    required String emergencyContact,
  }) async {
    emit(AuthLoading());
    try {
      final data = await _api.register(
        email: email,
        password: password,
        displayName: displayName,
        emergencyContact: emergencyContact,
      );
      final needsConfirm = data['requires_email_confirmation'] == true;
      final token = data['access_token'] as String?;
      if (needsConfirm || token == null || token.isEmpty) {
        emit(
          AuthNeedsConfirmation(
            data['email'] as String? ?? email,
            data['message'] as String? ??
                'Check your email to confirm the account',
          ),
        );
        return;
      }
      _api.setToken(token);
      emit(
        AuthAuthenticated(
          userId: data['user_id'] as String,
          email: data['email'] as String? ?? email,
          token: token,
        ),
      );
    } catch (e) {
      emit(AuthError(_friendly(e)));
    }
  }

  Future<bool> resendVerification(String email) async {
    try {
      await _api.resendVerification(email);
      return true;
    } catch (_) {
      return false;
    }
  }

  void logout() {
    _api.setToken(null);
    emit(AuthInitial());
  }

  String _friendly(Object e) {
    final s = e.toString().toLowerCase();
    if (s.contains('409')) return 'Email already registered';
    if (s.contains('400')) return 'Signup failed — check email/password';
    if (s.contains('401')) return 'Invalid email or password';
    if (s.contains('blocked') || s.contains('prohibited')) {
      return ApiClient.friendlyError(e);
    }
    if (s.contains('not verified') || s.contains('email')) {
      return 'Please verify your email before signing in.';
    }
    if (s.contains('403')) {
      return ApiClient.friendlyError(e);
    }
    return ApiClient.friendlyError(e);
  }
}