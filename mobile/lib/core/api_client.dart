import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart';

class ApiClient {
  ApiClient({required this.baseUrl})
    : _dio = Dio(
        BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 30),
          receiveTimeout: const Duration(seconds: 45),
          sendTimeout: const Duration(seconds: 45),
        ),
      ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final token = _token;
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
      ),
    );
  }

  final String baseUrl;
  final Dio _dio;
  String? _token;

  void setToken(String? token) {
    _token = token;
    if (token == null || token.isEmpty) {
      _dio.options.headers.remove('Authorization');
    } else {
      _dio.options.headers['Authorization'] = 'Bearer $token';
    }
  }

  /// Short, user-facing message for Dio / network failures (no raw stack).
  static String friendlyError(Object error) {
    if (error is DioException) {
      switch (error.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.sendTimeout:
        case DioExceptionType.receiveTimeout:
          return 'Connection timed out. Check the API is running and try again.';
        case DioExceptionType.connectionError:
          return 'Cannot reach the server. Check Wi‑Fi / emulator API URL.';
        case DioExceptionType.badResponse:
          final detail = _responseDetail(error.response?.data);
          final code = error.response?.statusCode;
          switch (code) {
            case 401:
              return 'Your session has expired. Please sign in again.';
            case 403:
              if (detail != null && detail.isNotEmpty) return detail;
              return 'Access denied. Your account may be blocked or unverified.';
            case 422:
              if (detail != null && detail.isNotEmpty) return detail;
              return 'This report was not posted. Check for prohibited content.';
            case 503:
              return 'Service temporarily unavailable. Try again soon.';
            default:
              if (detail != null && detail.isNotEmpty) return detail;
              return 'Server error. Try again.';
          }
        case DioExceptionType.cancel:
          return 'Request cancelled.';
        default:
          return 'Network error. Try again.';
      }
    }
    return 'Something went wrong. Please try again.';
  }

  static String? _responseDetail(Object? data) {
    if (data == null) return null;
    if (data is String && data.trim().isNotEmpty) return data.trim();
    if (data is Map) {
      final raw = data['detail'];
      if (raw is String && raw.trim().isNotEmpty) return raw.trim();
      if (raw is List && raw.isNotEmpty) {
        final first = raw.first;
        if (first is Map && first['msg'] != null) {
          return first['msg'].toString();
        }
        return first.toString();
      }
    }
    return null;
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    final res = await _dio.post(
      '/api/v1/auth/login',
      data: {'email': email, 'password': password},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> register({
    required String email,
    required String password,
    String? displayName,
    required String emergencyContact,
  }) async {
    final res = await _dio.post(
      '/api/v1/auth/register',
      data: {
        'email': email,
        'password': password,
        if (displayName != null && displayName.isNotEmpty)
          'display_name': displayName,
        'emergency_contact': emergencyContact,
      },
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> resendVerification(String email) async {
    final res = await _dio.post(
      '/api/v1/auth/resend-verification',
      data: {'email': email},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> forgotPassword(String email) async {
    final res = await _dio.post(
      '/api/v1/auth/forgot-password',
      data: {'email': email},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    final res = await _dio.post(
      '/api/v1/auth/change-password',
      data: {
        'current_password': currentPassword,
        'new_password': newPassword,
      },
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> createReport(Map<String, dynamic> body) async {
    final res = await _dio.post('/api/v1/reports', data: body);
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> nearbyReports({
    required double lat,
    required double lon,
    int radiusM = 5000,
    String? reportType,
  }) async {
    final res = await _dio.get(
      '/api/v1/reports/nearby',
      queryParameters: {
        'lat': lat,
        'lon': lon,
        'radius_m': radiusM,
        if (reportType != null) 'report_type': reportType,
      },
      options: Options(
        headers: {
          if (_token != null && _token!.isNotEmpty)
            'Authorization': 'Bearer $_token',
        },
      ),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> uploadReportImage({
    required String reportId,
    required List<int> bytes,
    required String filename,
    bool isPrimary = true,
  }) async {
    final contentType = _mimeFromFilename(filename);
    final form = FormData.fromMap({
      'is_primary': isPrimary.toString(),
      'file': MultipartFile.fromBytes(
        bytes,
        filename: filename,
        contentType: MediaType.parse(contentType),
      ),
    });
    final res = await _dio.post('/api/v1/reports/$reportId/images', data: form);
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getAIStatus(String reportId) async {
    final res = await _dio.get('/api/v1/reports/$reportId/ai-status');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getReport(String reportId) async {
    final res = await _dio.get('/api/v1/reports/$reportId');
    return Map<String, dynamic>.from(res.data as Map);
  }

  String _mimeFromFilename(String filename) {
    final lower = filename.toLowerCase();
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.webp')) return 'image/webp';
    if (lower.endsWith('.gif')) return 'image/gif';
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
    if (lower.endsWith('.m4a')) return 'audio/mp4';
    if (lower.endsWith('.aac')) return 'audio/aac';
    if (lower.endsWith('.mp3')) return 'audio/mpeg';
    if (lower.endsWith('.wav')) return 'audio/wav';
    if (lower.endsWith('.ogg')) return 'audio/ogg';
    if (lower.endsWith('.webm')) return 'audio/webm';
    return 'application/octet-stream';
  }

  // ---------------------------------------------------------------------------
  // Sprint 4 — Matches + Notifications
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> getReportMatches(
    String reportId, {
    String minBand = 'LOW',
    int limit = 20,
  }) async {
    final res = await _dio.get(
      '/api/v1/reports/$reportId/matches',
      queryParameters: {'min_band': minBand, 'limit': limit},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getNotifications({
    bool unreadOnly = false,
    int limit = 50,
  }) async {
    final res = await _dio.get(
      '/api/v1/notifications',
      queryParameters: {'unread_only': unreadOnly, 'limit': limit},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<void> markNotificationRead(String notificationId) async {
    await _dio.patch('/api/v1/notifications/$notificationId/read');
  }

  Future<Map<String, dynamic>> getMe() async {
    final res = await _dio.get('/api/v1/auth/me');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<void> pingLocation({required double lat, required double lon}) async {
    await _dio.post(
      '/api/v1/auth/me/location',
      data: {'latitude': lat, 'longitude': lon},
    );
  }

  Future<Map<String, dynamic>> listMyReports({
    String? reportType,
    String? status,
    int limit = 50,
  }) async {
    final res = await _dio.get(
      '/api/v1/reports',
      queryParameters: {
        if (reportType != null) 'report_type': reportType,
        if (status != null) 'status': status,
        'limit': limit,
      },
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  // ---------------------------------------------------------------------------
  // Sprint 5 — Claims + Verification + Chat
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> listChatRooms() async {
    final res = await _dio.get('/api/v1/chat/rooms');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> startClaim({
    required String matchId,
    required String foundReportId,
  }) async {
    final res = await _dio.post(
      '/api/v1/matches/$matchId/claim',
      data: {'match_id': matchId, 'found_report_id': foundReportId},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> submitAnswers({
    required String verificationSessionId,
    required String claimAttemptId,
    required List<String> answers,
  }) async {
    final res = await _dio.post(
      '/api/v1/claims/$verificationSessionId/answer',
      data: {'claim_attempt_id': claimAttemptId, 'answers': answers},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getClaimStatus(String attemptId) async {
    final res = await _dio.get('/api/v1/claims/$attemptId/status');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getChatRoomByMatch(String matchId) async {
    final res = await _dio.get('/api/v1/chat/rooms/by-match/$matchId');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getChatRoom(String roomId) async {
    final res = await _dio.get('/api/v1/chat/rooms/$roomId');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getChatMessages(
    String roomId, {
    int limit = 50,
  }) async {
    final res = await _dio.get(
      '/api/v1/chat/rooms/$roomId/messages',
      queryParameters: {'limit': limit},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> sendChatMessage(
    String roomId,
    String body,
  ) async {
    final res = await _dio.post(
      '/api/v1/chat/rooms/$roomId/messages',
      data: {'body': body},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> sendChatMedia({
    required String roomId,
    required List<int> bytes,
    required String filename,
    required String messageType,
    String? caption,
  }) async {
    final contentType = _mimeFromFilename(filename);
    final form = FormData.fromMap({
      'message_type': messageType,
      if (caption != null && caption.isNotEmpty) 'caption': caption,
      'file': MultipartFile.fromBytes(
        bytes,
        filename: filename,
        contentType: MediaType.parse(contentType),
      ),
    });
    final res = await _dio.post(
      '/api/v1/chat/rooms/$roomId/media',
      data: form,
      options: Options(receiveTimeout: const Duration(seconds: 60)),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Uri chatWebSocketUri(String roomId) {
    final base = baseUrl.replaceFirst(RegExp(r'^http'), 'ws');
    final token = _token ?? '';
    return Uri.parse('$base/ws/chat/$roomId?token=$token');
  }

  /// Lost + found finished handover — hides both posts from public feeds.
  Future<Map<String, dynamic>> completeHandover(String roomId) async {
    final res = await _dio.post('/api/v1/chat/rooms/$roomId/handover-complete');
    return Map<String, dynamic>.from(res.data as Map);
  }

  /// Owner self-find / withdraw — hides this post. Does not delete it.
  Future<Map<String, dynamic>> closeReport(
    String reportId, {
    String reason = 'self_found',
  }) async {
    final res = await _dio.post(
      '/api/v1/reports/$reportId/close',
      data: {'reason': reason},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }
}
