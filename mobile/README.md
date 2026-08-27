# VERIFIND mobile — Sprint 4: Zero-Fraud matches + notifications

## Prerequisites (Windows)

| Tool | Version | Notes |
|------|---------|-------|
| **Flutter** | **3.38.5** (stable) | Pin via FVM — matches team global Flutter |
| **FVM** | latest | https://fvm.app/documentation/getting-started/installation |
| **JDK** | **17** (e.g. 17.0.12) | Android Gradle uses Java 17 (`mobile/android/app/build.gradle.kts`) |
| **Android Studio** | recent | SDK + emulator optional |

### One-time setup (FVM)

From repo root:

```powershell
cd mobile
fvm install
fvm use 3.38.5
fvm flutter --version
```

Expected: `Flutter 3.38.5` / `Dart 3.10.4`.

Set `JAVA_HOME` to JDK 17 if Gradle fails (e.g. `C:\Program Files\Java\jdk-17.0.12`).

### Dependencies

```powershell
cd mobile
fvm flutter pub get
```

Or from repo root: `make mobile-get` (uses FVM when `.fvm/fvm_config.json` exists).

## Android device (team)

Requires: FVM, Flutter 3.38.5, JDK 17, Android SDK

```powershell
cd mobile
fvm install
fvm flutter pub get
fvm flutter run --dart-define=API_BASE_URL=http://<YOUR-PC-LAN-IP>:8000
```

Use your PC's LAN IP from `ipconfig` (not `localhost` or `10.0.2.2` on a physical phone).

Gradle clean if build fails after pull:

```powershell
cd android
.\gradlew --stop
cd ..
fvm flutter clean
```

### Run (other targets)

**Chrome on Windows:** bind IPv4 and skip the CanvasKit CDN, or DWDS `Debugger.enable` times out after a long compile.

```powershell
fvm flutter run -d chrome --web-hostname 127.0.0.1 --no-web-resources-cdn --dart-define=API_BASE_URL=http://localhost:8000
```

If Chrome still fails to attach the debug service, skip Chrome CDP:

```powershell
fvm flutter run -d web-server --web-hostname 127.0.0.1 --web-port 8080 --dart-define=API_BASE_URL=http://localhost:8000
```

Then open http://127.0.0.1:8080

**Windows desktop:**

```powershell
fvm flutter run -d windows --dart-define=API_BASE_URL=http://localhost:8000
```

**Android emulator → host API:**

```powershell
fvm flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

VS Code / Cursor: open the repo folder; `.vscode/settings.json` points Dart at `mobile/.fvm/flutter_sdk` after `fvm install`.

## Screens

- Login / Register (Supabase Auth)
- My Reports — list with AI Status + Matches buttons
- Nearby — spatial reports feed
- Notifications — HIGH/MEDIUM match alerts with unread badge
- Create Report (FAB) — GPS fuzz ±500m, photo upload
- AI Status — real-time AI pipeline polling
- Matches — per-report fusion scored candidates
