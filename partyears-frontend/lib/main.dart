import 'package:flutter/material.dart';
import 'app/party_ears_app.dart';
import 'core/network/red.dart';

Future<void> main() async {
    WidgetsFlutterBinding.ensureInitialized();
    await Red.iniciar();
    runApp(const PartyEarsApp());
}