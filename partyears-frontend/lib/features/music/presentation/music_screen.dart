import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/network/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/common.dart';
import '../../queue/mi_cola.dart';
import '../../queue/presentation/queue_screen.dart';
import '../data/catalogo_service.dart';

/// Catálogo (RF-03): búsqueda por título o artista, de 20 en 20, y aportación a la cola
/// individual (RF-05) con la variante elegida (RF-25).
class MusicScreen extends StatefulWidget {
    const MusicScreen({
        super.key,
        required this.inParty,
        required this.controlador,
        required this.buscarPagina,
        this.onAbrirParty,
    });

    final bool inParty;
    final ControladorMiCola controlador;
    final Future<PaginaCatalogo> Function(String texto, int pagina) buscarPagina;
    final VoidCallback? onAbrirParty;

    @override
    State<MusicScreen> createState() => _MusicScreenState();
}

class _MusicScreenState extends State<MusicScreen> {
    static const _espera = Duration(milliseconds: 300);

    final _canciones = <CancionCatalogo>[];
    String _texto = '';
    int _pagina = 0;
    int _total = 0;
    bool _hayMas = false;
    bool _buscando = false;
    String? _error;
    Timer? _temporizador;
    int _busqueda = 0;

    @override
    void initState() {
        super.initState();
        _buscar('');
    }

    @override
    void dispose() {
        _temporizador?.cancel();
        super.dispose();
    }

    void _alEscribir(String texto) {
        _temporizador?.cancel();
        _temporizador = Timer(_espera, () => _buscar(texto));
    }

    Future<void> _buscar(String texto, {bool siguiente = false}) async {
        final busqueda = ++_busqueda;
        final pagina = siguiente ? _pagina + 1 : 1;
        setState(() {
            _buscando = true;
            if (!siguiente) _texto = texto.trim();
        });
        try {
            final resultado = await widget.buscarPagina(_texto, pagina);
            // An older search answering late must not replace a newer one.
            if (!mounted || busqueda != _busqueda) return;
            setState(() {
                if (!siguiente) _canciones.clear();
                _canciones.addAll(resultado.resultados);
                _pagina = resultado.pagina;
                _total = resultado.total;
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

    Future<void> _agregar(VarianteAudio variante, {required bool reproducir}) async {
        final mensaje = await widget.controlador.agregar(variante.recursoAudioId, reproducirSiNoSuena: reproducir);
        if (!mounted) return;
        final texto = mensaje ?? widget.controlador.error;
        widget.controlador.error = null;
        if (texto != null) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(texto)));
    }

    void _abrirCola() {
        Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => QueueScreen(controlador: widget.controlador)));
    }

    @override
    Widget build(BuildContext context) {
        final gap = isCompact(context) ? 20.0 : 40.0;
        return ListView(
            padding: EdgeInsets.fromLTRB(gap, gap, gap, 32),
            children: [
                Wrap(
                    alignment: WrapAlignment.spaceBetween,
                    crossAxisAlignment: WrapCrossAlignment.end,
                    runSpacing: 12,
                    children: [
                        const PageHeader(
                            eyebrow: 'Explora y descubre',
                            title: 'Catálogo musical',
                            subtitle: 'Busca canciones por título o artista y agrégalas a tu cola.',
                        ),
                        if (!widget.inParty)
                            ListenableBuilder(
                                listenable: widget.controlador,
                                builder: (context, _) => FilledButton.icon(
                                    onPressed: _abrirCola,
                                    icon: const Icon(Icons.queue_music, size: 18),
                                    label: Text('Mi cola (${widget.controlador.pendientes.length})'),
                                ),
                            ),
                    ],
                ),
                if (widget.inParty) ...[
                    const SizedBox(height: 20),
                    _AvisoParty(onAbrirParty: widget.onAbrirParty),
                ],
                const SizedBox(height: 24),
                TextField(
                    onChanged: _alEscribir,
                    decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.search, color: AppColors.muted),
                        hintText: 'Buscar por canción o artista...',
                    ),
                ),
                const SizedBox(height: 28),
                Row(
                    children: [
                        Expanded(
                            child: Text(
                                _texto.isEmpty ? 'Todo el catálogo' : 'Resultados',
                                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                            ),
                        ),
                        Text(
                            '$_total ${_total == 1 ? 'resultado' : 'resultados'}',
                            style: const TextStyle(color: AppColors.muted, fontSize: 12),
                        ),
                    ],
                ),
                const SizedBox(height: 16),
                if (_buscando && _canciones.isEmpty) const LinearProgressIndicator(),
                if (_error != null)
                    Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    ),
                Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                        color: AppColors.surface,
                        border: Border.all(color: AppColors.border),
                        borderRadius: BorderRadius.circular(16),
                    ),
                    child: _canciones.isEmpty
                        ? Padding(
                            padding: const EdgeInsets.all(24),
                            child: Text(
                                _buscando ? 'Buscando...' : 'No se encontraron canciones',
                                textAlign: TextAlign.center,
                                style: const TextStyle(color: AppColors.muted),
                            ),
                        )
                        : Column(
                            children: [
                                for (var i = 0; i < _canciones.length; i++) ...[
                                    if (i > 0) const Divider(height: 1),
                                    _SongRow(
                                        cancion: _canciones[i],
                                        puedeAgregar: !widget.inParty,
                                        onAgregar: (v) => _agregar(v, reproducir: false),
                                        onReproducir: (v) => _agregar(v, reproducir: true),
                                    ),
                                ],
                            ],
                        ),
                ),
                if (_hayMas) ...[
                    const SizedBox(height: 16),
                    Center(
                        child: OutlinedButton(
                            onPressed: _buscando ? null : () => _buscar(_texto, siguiente: true),
                            child: Text(_buscando ? 'Cargando...' : 'Cargar más'),
                        ),
                    ),
                ],
            ],
        );
    }
}

/// PRE-03 de CU-25: dentro de una party no se usa la cola individual.
class _AvisoParty extends StatelessWidget {
    const _AvisoParty({this.onAbrirParty});

    final VoidCallback? onAbrirParty;

    @override
    Widget build(BuildContext context) {
        return Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.12),
                border: Border.all(color: AppColors.primary.withValues(alpha: 0.4)),
                borderRadius: BorderRadius.circular(12),
            ),
            child: Wrap(
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 12,
                runSpacing: 8,
                children: [
                    const Text('Estás en una party: las canciones se agregan desde la pantalla de la party.'),
                    if (onAbrirParty != null) TextButton(onPressed: onAbrirParty, child: const Text('Ir a la party')),
                ],
            ),
        );
    }
}

class _SongRow extends StatefulWidget {
    const _SongRow({
        required this.cancion,
        required this.puedeAgregar,
        required this.onAgregar,
        required this.onReproducir,
    });

    final CancionCatalogo cancion;
    final bool puedeAgregar;
    final ValueChanged<VarianteAudio> onAgregar;
    final ValueChanged<VarianteAudio> onReproducir;

    @override
    State<_SongRow> createState() => _SongRowState();
}

class _SongRowState extends State<_SongRow> {
    bool _instrumental = false;

    @override
    Widget build(BuildContext context) {
        final cancion = widget.cancion;
        final instrumental = cancion.instrumental;
        final variante = _instrumental && instrumental != null ? instrumental : (cancion.original ?? instrumental);

        return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
            child: Row(
                children: [
                    AlbumCover(color: colorDePortada(cancion.titulo)),
                    const SizedBox(width: 14),
                    Expanded(
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                                Text(cancion.titulo, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                                const SizedBox(height: 2),
                                Text(cancion.nombreArtistas, style: const TextStyle(color: AppColors.muted, fontSize: 11)),
                                if (instrumental != null && widget.puedeAgregar)
                                    Padding(
                                        padding: const EdgeInsets.only(top: 6),
                                        child: FilterChip(
                                            label: const Text('Instrumental'),
                                            selected: _instrumental,
                                            onSelected: (v) => setState(() => _instrumental = v),
                                            visualDensity: VisualDensity.compact,
                                        ),
                                    ),
                            ],
                        ),
                    ),
                    Text(
                        formatearDuracion(Duration(milliseconds: cancion.duracionMs)),
                        style: const TextStyle(color: AppColors.muted, fontSize: 12),
                    ),
                    if (widget.puedeAgregar && variante != null) ...[
                        const SizedBox(width: 8),
                        IconButton(
                            tooltip: 'Reproducir',
                            onPressed: () => widget.onReproducir(variante),
                            icon: const Icon(Icons.play_arrow, size: 18),
                        ),
                        IconButton(
                            tooltip: 'Agregar a mi cola',
                            onPressed: () => widget.onAgregar(variante),
                            style: IconButton.styleFrom(
                                backgroundColor: const Color(0xFF2A2440),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                            ),
                            icon: const Icon(Icons.add, size: 18),
                        ),
                    ],
                ],
            ),
        );
    }
}
