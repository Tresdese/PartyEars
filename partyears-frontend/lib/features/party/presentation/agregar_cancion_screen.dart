import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/network/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../music/data/catalogo_service.dart';

/// P-06: buscar en el catálogo y agregar una variante disponible a la cola de la party (CU-11).
class AgregarCancionScreen extends StatefulWidget {
    const AgregarCancionScreen({super.key, required this.buscar, required this.agregar});

    final Future<List<CancionCatalogo>> Function(String texto) buscar;

    /// Devuelve el mensaje que se muestra al usuario.
    final Future<String> Function(String recursoAudioId) agregar;

    @override
    State<AgregarCancionScreen> createState() => _AgregarCancionScreenState();
}

class _AgregarCancionScreenState extends State<AgregarCancionScreen> {
    List<CancionCatalogo> _resultados = const [];
    String? _error;
    bool _buscando = false;
    String? _agregando;
    Timer? _espera;
    int _busqueda = 0;

    @override
    void initState() {
        super.initState();
        _buscar('');
    }

    @override
    void dispose() {
        _espera?.cancel();
        super.dispose();
    }

    Future<void> _buscar(String texto) async {
        final busqueda = ++_busqueda;
        setState(() => _buscando = true);
        try {
            final resultados = await widget.buscar(texto.trim());
            // An older search answering late must not replace a newer one.
            if (!mounted || busqueda != _busqueda) return;
            setState(() {
                _resultados = resultados;
                _error = null;
            });
        } on ApiException catch (e) {
            if (!mounted || busqueda != _busqueda) return;
            setState(() => _error = e.mensaje);
        } finally {
            if (mounted && busqueda == _busqueda) setState(() => _buscando = false);
        }
    }

    Future<void> _agregar(VarianteAudio variante) async {
        setState(() => _agregando = variante.recursoAudioId);
        final mensaje = await widget.agregar(variante.recursoAudioId);
        if (!mounted) return;
        setState(() => _agregando = null);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(mensaje)));
    }

    @override
    Widget build(BuildContext context) {
        return Scaffold(
            appBar: AppBar(title: const Text('Agregar a la cola de la party')),
            body: ListView(
                padding: const EdgeInsets.all(24),
                children: [
                    TextField(
                        autofocus: true,
                        decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Buscar por canción o artista...'),
                        onChanged: (texto) {
                            _espera?.cancel();
                            _espera = Timer(const Duration(milliseconds: 300), () => _buscar(texto));
                        },
                    ),
                    const SizedBox(height: 16),
                    if (_buscando) const LinearProgressIndicator(),
                    if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    if (!_buscando && _error == null && _resultados.isEmpty)
                        const ListTile(title: Text('No se encontraron canciones')),
                    for (final cancion in _resultados)
                        for (final variante in cancion.variantes)
                            ListTile(
                                title: Text(variante.tipo == 'instrumental' ? '${cancion.titulo} (instrumental)' : cancion.titulo),
                                subtitle: Text(cancion.artistas.join(', '), style: const TextStyle(color: AppColors.muted)),
                                trailing: variante.disponible
                                    ? FilledButton(
                                        onPressed: _agregando == null ? () => _agregar(variante) : null,
                                        child: const Text('Agregar a la cola'),
                                    )
                                    : const Text('No disponible', style: TextStyle(color: AppColors.muted)),
                            ),
                ],
            ),
        );
    }
}
