import 'package:flutter_bloc/flutter_bloc.dart';

import '../../core/api_client.dart';

/// Tracks whether the signed-in app user is allowed to post.
class AccountStatusState {
  const AccountStatusState({
    this.isActive = true,
    this.loaded = false,
  });

  final bool isActive;
  final bool loaded;

  bool get isBlocked => loaded && !isActive;

  AccountStatusState copyWith({bool? isActive, bool? loaded}) {
    return AccountStatusState(
      isActive: isActive ?? this.isActive,
      loaded: loaded ?? this.loaded,
    );
  }
}

class AccountStatusCubit extends Cubit<AccountStatusState> {
  AccountStatusCubit(this._api) : super(const AccountStatusState());

  final ApiClient _api;

  Future<void> refresh({bool silent = false}) async {
    try {
      final me = await _api.getMe();
      final active = me['is_active'] as bool? ?? true;
      emit(AccountStatusState(isActive: active, loaded: true));
    } catch (_) {
      if (!silent && !state.loaded) {
        // Keep previous assumption (active) so we never flash a false block.
        emit(state.copyWith(loaded: true, isActive: true));
      }
    }
  }

  void markBlocked() {
    emit(const AccountStatusState(isActive: false, loaded: true));
  }
}
