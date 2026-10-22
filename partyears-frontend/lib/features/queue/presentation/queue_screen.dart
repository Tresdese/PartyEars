import 'package:flutter/material.dart';

class QueueScreen extends StatelessWidget {
  const QueueScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Cola de la Party')),
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Aquí se mostrará la cola de canciones y los votos para saltar.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
