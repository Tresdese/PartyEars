import 'package:flutter/material.dart';

class VoiceScreen extends StatelessWidget {
  const VoiceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Sala de voz')),
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.mic_off_outlined, size: 64),
              SizedBox(height: 12),
              Text('La transmisión de voz todavía no está implementada.'),
              SizedBox(height: 12),
              Text('Aquí integraremos permisos de micrófono y WebRTC.'),
            ],
          ),
        ),
      ),
    );
  }
}
