import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';
import 'app/party_ears_app.dart';
import 'core/network/red.dart';

Future<void> main() async {
    WidgetsFlutterBinding.ensureInitialized();
    MediaKit.ensureInitialized();
    await Red.iniciar();
    runApp(const PartyEarsApp());
}