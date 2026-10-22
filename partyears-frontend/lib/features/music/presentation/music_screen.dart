import 'package:flutter/material.dart';

class MusicScreen extends StatelessWidget {
  const MusicScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: const [
        TextField(
          decoration: InputDecoration(
            prefixIcon: Icon(Icons.search),
            labelText: 'Buscar canciones o artistas',
          ),
        ),
        SizedBox(height: 24),
        ListTile(
          leading: Icon(Icons.library_music),
          title: Text('Catálogo musical'),
          subtitle: Text('Aquí se mostrarán las canciones del backend.'),
        ),
      ],
    );
  }
}
