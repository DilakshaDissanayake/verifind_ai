import 'package:flutter/material.dart';
import 'package:phosphoricons_flutter/phosphoricons_flutter.dart';

/// Semantic icon map. Screens should reference `AppIcons.x` instead of
/// importing `phosphoricons_flutter` directly — keeps the icon language
/// consistent and lets us swap the underlying icon set in one place.
class AppIcons {
  AppIcons._();

  // Navigation
  static IconData myReports({bool active = false}) =>
      active ? PhosphorIconsFill.houseLine : PhosphorIconsRegular.houseLine;
  static IconData nearby({bool active = false}) =>
      active ? PhosphorIconsFill.compass : PhosphorIconsRegular.compass;
  static IconData notifications({bool active = false}) =>
      active ? PhosphorIconsFill.bellSimple : PhosphorIconsRegular.bellSimple;

  // Actions
  static const IconData addReport = PhosphorIconsBold.cameraPlus;
  static const IconData camera = PhosphorIconsRegular.camera;
  static const IconData gallery = PhosphorIconsRegular.imageSquare;
  static const IconData refresh = PhosphorIconsRegular.arrowsClockwise;
  // Prefer Material send — Phosphor fill can render empty inside IconButton.filled.
  static const IconData send = Icons.send_rounded;
  static const IconData trash = PhosphorIconsRegular.trash;
  static const IconData plusCircle = PhosphorIconsRegular.plusCircle;
  static const IconData signOut = PhosphorIconsRegular.signOut;
  static const IconData caretRight = PhosphorIconsBold.caretRight;
  static const IconData link = PhosphorIconsRegular.linkSimple;

  // Report type / domain
  static const IconData lost = PhosphorIconsBold.magnifyingGlass;
  static const IconData found = PhosphorIconsBold.package;
  static const IconData mapPin = PhosphorIconsFill.mapPin;
  static const IconData gps = PhosphorIconsBold.crosshairSimple;
  static const IconData distance = PhosphorIconsFill.navigationArrow;

  // AI / verification
  static const IconData sparkle = PhosphorIconsFill.sparkle;
  static const IconData brain = PhosphorIconsBold.brain;
  static const IconData shieldCheck = PhosphorIconsFill.shieldCheck;
  static const IconData fingerprint = PhosphorIconsBold.fingerprint;
  static const IconData blur = PhosphorIconsRegular.eyeSlash;
  static const IconData tag = PhosphorIconsRegular.tag;
  static const IconData matches = PhosphorIconsBold.arrowsLeftRight;
  static const IconData target = PhosphorIconsBold.target;

  // Status / feedback
  static const IconData checkCircle = PhosphorIconsFill.checkCircle;
  static const IconData warningCircle = PhosphorIconsFill.warningCircle;
  static const IconData xCircle = PhosphorIconsFill.xCircle;
  static const IconData clock = PhosphorIconsBold.clockCountdown;
  static const IconData imageBroken = PhosphorIconsRegular.imageBroken;
  static const IconData bellOff = PhosphorIconsRegular.bellSlash;
  static const IconData wifiOn = PhosphorIconsFill.wifiHigh;
  static const IconData wifiOff = PhosphorIconsBold.wifiSlash;

  // Auth
  static const IconData email = PhosphorIconsRegular.envelopeSimple;
  static const IconData lock = PhosphorIconsRegular.lockKey;
  static const IconData user = PhosphorIconsRegular.userCircle;
    static const IconData phone = PhosphorIconsRegular.phone;
  static const IconData eye = PhosphorIconsRegular.eye;
  static const IconData eyeSlash = PhosphorIconsRegular.eyeSlash;

  // Chat
  static const IconData chat = PhosphorIconsFill.chatCircleDots;
  static const IconData verifiedBadge = PhosphorIconsFill.sealCheck;
  static const IconData mic = PhosphorIconsFill.microphone;
  static const IconData micOff = PhosphorIconsRegular.microphoneSlash;
  static const IconData image = PhosphorIconsRegular.image;
  static const IconData play = PhosphorIconsFill.play;
  static const IconData stop = PhosphorIconsFill.stop;
  static const IconData attach = PhosphorIconsRegular.paperclip;
}
