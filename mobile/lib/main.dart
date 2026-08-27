import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'design/app_colors.dart';
import 'design/app_icons.dart';
import 'design/app_spacing.dart';
import 'design/app_theme.dart';
import 'core/api_client.dart';
import 'core/app_prefs.dart';
import 'features/auth/account_status_cubit.dart';
import 'features/auth/auth_cubit.dart';
import 'features/auth/login_page.dart';
import 'features/chat/chats_page.dart';
import 'features/matches/notifications_cubit.dart';
import 'features/matches/notifications_page.dart';
import 'features/onboarding/onboarding_page.dart';
import 'features/onboarding/permissions_page.dart';
import 'features/onboarding/splash_page.dart';
import 'features/profile/profile_page.dart';
import 'features/reports/create_report_page.dart';
import 'features/reports/my_reports_page.dart';
import 'features/reports/nearby_page.dart';
import 'widgets/dock_nav.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Draw behind system bars so SafeArea / viewPadding can reserve real insets
  // (avoids Android nav bar overlapping the floating dock).
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      systemNavigationBarColor: Colors.transparent,
      systemNavigationBarDividerColor: Colors.transparent,
      systemNavigationBarContrastEnforced: false,
      statusBarIconBrightness: Brightness.dark,
      systemNavigationBarIconBrightness: Brightness.dark,
    ),
  );
  runApp(const VerifindApp());
}

class VerifindApp extends StatelessWidget {
  const VerifindApp({super.key});

  @override
  Widget build(BuildContext context) {
    return RepositoryProvider(
      create: (_) => ApiClient(
        baseUrl: const String.fromEnvironment(
          'API_BASE_URL',
          defaultValue: 'http://10.0.2.2:8000',
        ),
      ),
      child: BlocProvider(
        create: (ctx) => AuthCubit(ctx.read<ApiClient>()),
        child: MaterialApp(
          title: 'VERIFIND',
          debugShowCheckedModeBanner: false,
          themeMode: ThemeMode.light,
          theme: AppTheme.light(),
          darkTheme: AppTheme.dark(),
          builder: (context, child) {
            return AnnotatedRegion<SystemUiOverlayStyle>(
              value: SystemUiOverlayStyle.dark.copyWith(statusBarColor: Colors.transparent),
              child: child ?? const SizedBox.shrink(),
            );
          },
          home: const _RootGate(),
        ),
      ),
    );
  }
}

/// Startup flow controller: Splash → (first run: Onboarding → Policy notice) →
/// authenticated app. The onboarding + consent notice is shown only once and
/// persisted via [AppPrefs].
class _RootGate extends StatefulWidget {
  const _RootGate();

  @override
  State<_RootGate> createState() => _RootGateState();
}

enum _Phase { splash, onboarding, permissions, ready }

class _RootGateState extends State<_RootGate> {
  final _prefs = AppPrefs();
  _Phase _phase = _Phase.splash;
  bool _onboarded = false;

  @override
  void initState() {
    super.initState();
    _prefs.hasOnboarded().then((value) {
      if (mounted) _onboarded = value;
    });
  }

  void _onSplashDone() {
    setState(() => _phase = _onboarded ? _Phase.ready : _Phase.onboarding);
  }

  void _onOnboardingDone() {
    setState(() => _phase = _Phase.permissions);
  }

  Future<void> _onPermissionsDone() async {
    await _prefs.setOnboarded();
    if (mounted) setState(() => _phase = _Phase.ready);
  }

  @override
  Widget build(BuildContext context) {
    final Widget child;
    switch (_phase) {
      case _Phase.splash:
        child = SplashPage(key: const ValueKey('splash'), onComplete: _onSplashDone);
        break;
      case _Phase.onboarding:
        child = OnboardingPage(
          key: const ValueKey('onboarding'),
          onDone: _onOnboardingDone,
        );
        break;
      case _Phase.permissions:
        child = PermissionsPage(
          key: const ValueKey('permissions'),
          onDone: _onPermissionsDone,
        );
        break;
      case _Phase.ready:
        child = const _AuthGate(key: ValueKey('auth'));
        break;
    }

    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 360),
      switchInCurve: Curves.easeOut,
      child: child,
    );
  }
}

/// Chooses between login and the authenticated home shell.
class _AuthGate extends StatelessWidget {
  const _AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AuthCubit, AuthState>(
      builder: (context, state) {
        return AnimatedSwitcher(
          duration: const Duration(milliseconds: 320),
          switchInCurve: Curves.easeOut,
          child: state is AuthAuthenticated
              ? const _HomeShell(key: ValueKey('home'))
              : const LoginPage(key: ValueKey('login')),
        );
      },
    );
  }
}

/// Home shell: Reports / Nearby / Chats / Alerts / Profile
class _HomeShell extends StatefulWidget {
  const _HomeShell({super.key});

  @override
  State<_HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<_HomeShell> {
  int _tab = 0;
  Timer? _poll;
  Timer? _accountPoll;

  static const _pages = [
    MyReportsPage(),
    NearbyPage(),
    ChatsPage(),
    NotificationsPage(),
    ProfilePage(),
  ];

  @override
  void dispose() {
    _poll?.cancel();
    _accountPoll?.cancel();
    super.dispose();
  }

  void _startPoll(NotificationsCubit cubit) {
    _poll?.cancel();
    _poll = Timer.periodic(const Duration(seconds: 8), (_) {
      if (!mounted) return;
      cubit.load(silent: true);
    });
  }

  void _startAccountPoll(AccountStatusCubit cubit) {
    _accountPoll?.cancel();
    _accountPoll = Timer.periodic(const Duration(seconds: 30), (_) {
      if (!mounted) return;
      cubit.refresh(silent: true);
    });
  }

  void _onTabSelected(
    int i,
    NotificationsCubit notifCubit,
    AccountStatusCubit accountCubit,
  ) {
    if (i == _tab) return;
    HapticFeedback.selectionClick();
    setState(() => _tab = i);
    if (i == 3) notifCubit.load();
    if (i == 4) accountCubit.refresh(silent: true);
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(
          create: (ctx) {
            final cubit = NotificationsCubit(ctx.read<ApiClient>())..load();
            _startPoll(cubit);
            return cubit;
          },
        ),
        BlocProvider(
          create: (ctx) {
            final cubit = AccountStatusCubit(ctx.read<ApiClient>())..refresh();
            _startAccountPoll(cubit);
            return cubit;
          },
        ),
      ],
      child: Builder(
        builder: (ctx) {
          final blocked = ctx.watch<AccountStatusCubit>().state.isBlocked;
          final statusColors = Theme.of(ctx).extension<AppStatusColors>()!;
          return Scaffold(
            extendBody: true,
            body: Column(
              children: [
                if (blocked)
                  Material(
                    color: statusColors.danger,
                    child: SafeArea(
                      bottom: false,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.md,
                          vertical: AppSpacing.sm,
                        ),
                        child: Row(
                          children: [
                            Icon(
                              AppIcons.warningCircle,
                              color: Colors.white,
                              size: 20,
                            ),
                            const SizedBox(width: AppSpacing.sm),
                            const Expanded(
                              child: Text(
                                'Account is blocked. Contact an administrator.',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w700,
                                  fontSize: 13,
                                  height: 1.3,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                Expanded(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 220),
                    child: KeyedSubtree(
                      key: ValueKey(_tab),
                      child: _pages[_tab],
                    ),
                  ),
                ),
              ],
            ),
            floatingActionButton: (_tab == 4 || blocked)
                ? null
                : Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: FloatingActionButton(
                      heroTag: 'fab_create',
                      tooltip: 'Report',
                      onPressed: () {
                        HapticFeedback.lightImpact();
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => RepositoryProvider.value(
                              value: context.read<ApiClient>(),
                              child: BlocProvider.value(
                                value: ctx.read<AccountStatusCubit>(),
                                child: const CreateReportPage(),
                              ),
                            ),
                          ),
                        );
                      },
                      child: Icon(AppIcons.addReport),
                    ),
                  ),
            bottomNavigationBar:
                BlocBuilder<NotificationsCubit, NotificationsState>(
              builder: (bctx, notifState) {
                final unread =
                    notifState is NotificationsLoaded ? notifState.unreadCount : 0;
                final notifCubit = bctx.read<NotificationsCubit>();
                final accountCubit = bctx.read<AccountStatusCubit>();
                return DockNav(
                  index: _tab,
                  unread: unread,
                  onSelect: (i) => _onTabSelected(i, notifCubit, accountCubit),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
