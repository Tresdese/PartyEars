import 'package:flutter/material.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text('Bienvenido a PartyEars',
            style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 12),
        const Text('Escucha música con otras personas y comparte una Party.'),
        const SizedBox(height: 24),
        const Card(
          child: ListTile(
            leading: Icon(Icons.music_note),
            title: Text('Explora el catálogo'),
            subtitle: Text('El catálogo se conectará al servicio Music.'),
          ),
        ),
        const Card(
          child: ListTile(
            leading: Icon(Icons.groups_outlined),
            title: Text('Crea una Party'),
            subtitle: Text('Invita a otras personas mediante un código.'),
          ),
        ),
      ],
    );
  }
}
