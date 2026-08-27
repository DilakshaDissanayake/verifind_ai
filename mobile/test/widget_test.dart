// Basic smoke test: a fresh app boots into the first-run onboarding flow.

import 'package:flutter_test/flutter_test.dart';

import 'package:verifind_mobile/main.dart';

void main() {
  testWidgets('VerifindApp boots into onboarding', (WidgetTester tester) async {
    await tester.pumpWidget(const VerifindApp());
    await tester.pumpAndSettle();

    expect(find.text('Report in seconds'), findsOneWidget);
    expect(find.text('Next'), findsOneWidget);
  });
}
