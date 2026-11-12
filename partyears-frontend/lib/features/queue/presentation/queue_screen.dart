import 'package:flutter/material.dart';

class QueueScreen extends StatelessWidget {
  const QueueScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Cola musical'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: FilledButton.icon(
              onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Agregar canción pendiente de conectar con Django'),
                ),
              ),
              icon: const Icon(Icons.add),
              label: const Text('Agregar canción'),
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text('ESCUCHA COLECTIVA', style: textTheme.labelMedium),
          const SizedBox(height: 4),
          Text('Cola musical', style: textTheme.headlineMedium),
          const SizedBox(height: 8),
          const Text(
            'Propón canciones y consulta el orden de reproducción.',
          ),
          const SizedBox(height: 24),
         
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Orden de reproducción', style: textTheme.titleLarge),
                          const Text('4 canciones · sala A7X2Q9'),
                        ],
                      ),
                      const Chip(label: Text('SINCRONIZADA')),
                    ],
                  ),
                  const SizedBox(height: 16),
                  const ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: CircleAvatar(child: Icon(Icons.volume_up)),
                    title: Text('Midnight City'),
                    subtitle: Text('M83 · Agregada por tresdese'),
                    trailing: Chip(label: Text('SONANDO')),
                  ),
                  const Divider(),
                  const ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: CircleAvatar(child: Text('02')),
                    title: Text('Blinding Lights'),
                    subtitle: Text('The Weeknd · Agregada por Ana'),
                    trailing: Text('3:20'),
                  ),
                  const Divider(),
                  const ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: CircleAvatar(child: Text('03')),
                    title: Text('After Dark'),
                    subtitle: Text('Mr.Kitty · Agregada por Ana'),
                    trailing: Text('4:17'),
                  ),
                  const Divider(),
                  const ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: CircleAvatar(child: Text('04')),
                    title: Text('Something About Us'),
                    subtitle: Text('Daft Punk · Agregada por Ana'),
                    trailing: Text('3:51'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            'PartyEars · Prototipo visual de navegación · Los datos y las acciones son simulados',
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}