import 'dart:io';

import 'package:flutter_foreground_task/flutter_foreground_task.dart';

/// Mantiene viva la app con la pantalla bloqueada mientras se está en una party (RF-21).
///
/// Foreground service instead of nothing: Android suspends a locked app, its heartbeat stops
/// and after 15 s the server marks the person disconnected (contract 7.4). The service also
/// holds a wake lock and a Wi-Fi lock so the socket and the audio keep going.
/// shortcut: Android only; iOS needs its own background audio mode, add it if the app ships there.
class SegundoPlano {
    static bool _iniciado = false;

    // Also false under flutter test, which runs on the host: the tests never reach the plugin.
    static bool get _disponible => Platform.isAndroid;

    static Future<void> mantener(String nombreParty) async {
        if (!_disponible) return;
        if (!_iniciado) {
            FlutterForegroundTask.init(
                androidNotificationOptions: AndroidNotificationOptions(
                    channelId: 'party_en_curso',
                    channelName: 'Party en curso',
                    channelDescription: 'Mantiene la conexión con la party con la pantalla bloqueada.',
                ),
                iosNotificationOptions: const IOSNotificationOptions(),
                foregroundTaskOptions: ForegroundTaskOptions(
                    eventAction: ForegroundTaskEventAction.nothing(),
                    allowWakeLock: true,
                    allowWifiLock: true,
                    allowAutoRestart: false,
                    stopWithTask: true,
                ),
            );
            _iniciado = true;
        }
        // Without the permission (Android 13+) the service still runs, only the notice is hidden.
        await FlutterForegroundTask.requestNotificationPermission();
        if (await FlutterForegroundTask.isRunningService) return;
        await FlutterForegroundTask.startService(
            serviceTypes: [ForegroundServiceTypes.mediaPlayback],
            notificationTitle: 'PartyEars',
            notificationText: 'Estás en $nombreParty',
        );
    }

    static Future<void> soltar() async {
        if (!_disponible || !await FlutterForegroundTask.isRunningService) return;
        await FlutterForegroundTask.stopService();
    }
}
