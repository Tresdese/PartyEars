import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/network/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../music/data/catalogo_service.dart';

/// P-06: buscar en el catálogo y agregar una variante disponible a la cola de la party (CU-11).
class AgregarCancionScreen extends StatefulWidget {
    const AgregarCancionScreen({super.key, required this.buscar, required this.agregar});

    /// Una página de la búsqueda (contrato 3.1); [pagina] cuenta desde 1.
    final Future<PaginaCatalogo> Function(String texto, int pagina) buscar;

    /// Devuelve el mensaje que se muestra al usuario.
    final Future<String> Function(String recursoAudioId) agregar;

    @override
    State<AgregarCancionScreen> createState() => _AgregarCancionScreenState();
}

class _AgregarCancionScreenState extends State<AgregarCancionScreen> {
    final _resultados = <CancionCatalogo>[];
    String _texto = '';
    int _pagina = 0;
    bool _hayMas = false;
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

    Future<void> _buscar(String texto, {bool siguiente = false}) async {
        final busqueda = ++_busqueda;
        final pagina = siguiente ? _pagina + 1 : 1;
        setState(() {
            _buscando = true;
            if (!siguiente) _texto = texto.trim();
        });
        try {
            final resultado = await widget.buscar(_texto, pagina);
            // An older search answering late must not replace a newer one.
            if (!mounted || busqueda != _busqueda) return;
            setState(() {
                if (!siguiente) _resultados.clear();
                _resultados.addAll(resultado.resultados);
                _pagina = resultado.pagina;
                _hayMas = resultado.hayMas;
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
                    if (_hayMas)
                        Padding(
                            padding: const EdgeInsets.only(top: 16),
                            child: Center(
                                child: OutlinedButton(
                                    onPressed: _buscando ? null : () => _buscar(_texto, siguiente: true),
                                    child: Text(_buscando ? 'Cargando...' : 'Cargar más'),
                                ),
                            ),
                        ),
                ],
            ),
        );
    }
}
