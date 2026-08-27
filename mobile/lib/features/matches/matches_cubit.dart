import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:verifind_mobile/core/api_client.dart';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

abstract class MatchesState extends Equatable {
  @override
  List<Object?> get props => [];
}

class MatchesInitial extends MatchesState {}

class MatchesLoading extends MatchesState {}

class MatchesLoaded extends MatchesState {
  MatchesLoaded({required this.items, required this.reportId});
  final List<Map<String, dynamic>> items;
  final String reportId;
  @override
  List<Object?> get props => [items, reportId];
}

class MatchesError extends MatchesState {
  MatchesError(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}

// ---------------------------------------------------------------------------
// Cubit
// ---------------------------------------------------------------------------

class MatchesCubit extends Cubit<MatchesState> {
  MatchesCubit(this._api) : super(MatchesInitial());
  final ApiClient _api;

  Future<void> loadMatches(String reportId, {String minBand = 'LOW'}) async {
    emit(MatchesLoading());
    try {
      final data = await _api.getReportMatches(reportId, minBand: minBand);
      final items = List<Map<String, dynamic>>.from(
        (data['items'] as List? ?? []).map(
          (e) => Map<String, dynamic>.from(e as Map),
        ),
      );
      emit(MatchesLoaded(items: items, reportId: reportId));
    } catch (e) {
      emit(MatchesError(_friendly(e)));
    }
  }

  String _friendly(Object e) {
    final s = e.toString();
    if (s.contains('503') || s.contains('Service Unavailable')) {
      return 'Server unavailable';
    }
    if (s.contains('401') || s.contains('Unauthorized')) {
      return 'Session expired — please log in again';
    }
    if (s.contains('SocketException') || s.contains('Connection refused')) {
      return 'Cannot reach server';
    }
    return ApiClient.friendlyError(e);
  }
}
