import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/common.dart';
import '../../party/data/cola_models.dart';
import '../mi_cola.dart';

/// Cola individual (CU-25 y RF-05): canción actual, controles y pendientes en orden.
class QueueScreen extends StatefulWidget {
    const QueueScreen({super.key, required this.controlador});

    final ControladorMiCola controlador;

    @override
    State<QueueScreen> createState() => _QueueScreenState();
}

class _QueueScreenState extends State<QueueScreen> {
    ControladorMiCola get _c => widget.controlador;

    @override
    void initState() {
        super.initState();
        _c.addListener(_mostrarError);
    }

    @override
    void dispose() {
        _c.removeListener(_mostrarError);
        super.dispose();
    }

    void _mostrarError() {
        final mensaje = _c.error;
        if (mensaje == null || !mounted) return;
        _c.error = null;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(mensaje)));
    }

    Future<void> _retirar(ElementoCola elemento) async {
        final titulo = _c.detalleDe(elemento.recursoAudioId)?.tituloConVariante ?? 'esta canción';
        final confirmado = await showDialog<bool>(
            context: context,
            builder: (contexto) => AlertDialog(
                title: const Text('Quitar de tu cola'),
                content: Text('¿Quitar $titulo de tu cola?'),
                actions: [
                    TextButton(onPressed: () => Navigator.of(contexto).pop(false), child: const Text('Cancelar')),
                    FilledButton(onPressed: () => Navigator.of(contexto).pop(true), child: const Text('Quitar')),
                ],
            ),
        );
        if (confirmado == true) await _c.retirar(elemento.id);
    }

    @override
    Widget build(BuildContext context) {
        return Scaffold(
            appBar: AppBar(
                title: const Text('Mi cola'),
                actions: [
                    Padding(
                        padding: const EdgeInsets.only(right: 12),
                        child: FilledButton.icon(
                            onPressed: () => Navigator.of(context).pop(),
                            icon: const Icon(Icons.add),
                            label: const Text('Agregar canciones'),
                        ),
                    ),
                ],
            ),
            body: ListenableBuilder(
                listenable: _c,
                builder: (context, _) => ListView(
                    padding: const EdgeInsets.all(24),
                    children: [
                        _Actual(controlador: _c),
                        const SizedBox(height: 24),
                        Text('Siguen', style: Theme.of(context).textTheme.titleLarge),
                        const SizedBox(height: 8),
                        if (_c.pendientes.isEmpty)
                            const Padding(
                                padding: EdgeInsets.symmetric(vertical: 24),
                                child: Text('No hay canciones pendientes en la cola',
                                            textAlign: TextAlign.center, style: TextStyle(color: AppColors.muted)),
                            ),
                        for (var i = 0; i < _c.pendientes.length; i++)
                            _Pendiente(
                                controlador: _c,
                                elemento: _c.pendientes[i],
                                posicion: i + 1,
                                total: _c.pendientes.length,
                                onRetirar: () => _retirar(_c.pendientes[i]),
                            ),
                    ],
                ),
            ),
        );
    }
}

class _Actual extends StatelessWidget {
    const _Actual({required this.controlador});

    final ControladorMiCola controlador;

    @override
    Widget build(BuildContext context) {
        final c = controlador;
        final recurso = c.reproduccion.recursoAudioId;
        final detalle = recurso == null ? null : c.detalleDe(recurso);
        final total = c.duracion;
        final maximo = total.inMilliseconds > 0 ? total.inMilliseconds.toDouble() : 1.0;
        final valor = c.posicion.inMilliseconds.clamp(0, maximo.toInt()).toDouble();

        return Card(
            child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                        Row(
                            children: [
                                AlbumCover(color: colorDePortada(detalle?.titulo ?? ''), size: 56),
                                const SizedBox(width: 16),
                                Expanded(
                                    child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                            Text(
                                                c.hayActual ? (detalle?.tituloConVariante ?? 'Canción') : 'Nada sonando',
                                                style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
                                            ),
                                            Text(
                                                c.hayActual ? (detalle?.nombreArtistas ?? '') : 'Presiona reproducir para empezar tu cola.',
                                                style: const TextStyle(color: AppColors.muted, fontSize: 12),
                                            ),
                                        ],
                                    ),
                                ),
                            ],
                        ),
                        if (c.hayActual) ...[
                            Slider(
                                value: valor,
                                max: maximo,
                                // Only on release instead of on every drag step: each change is a request to the server.
                                onChanged: c.ocupado ? null : (_) {},
                                onChangeEnd: (ms) => c.buscar(Duration(milliseconds: ms.round())),
                            ),
                            Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                    Text(formatearDuracion(c.posicion), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                                    Text(formatearDuracion(total), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                                ],
                            ),
                        ],
                        const SizedBox(height: 8),
                        // Wrap instead of Row: on a phone the volume goes under the buttons.
                        Wrap(
                            alignment: WrapAlignment.center,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            spacing: 12,
                            children: [
                                IconButton.filled(
                                    tooltip: c.sonando ? 'Pausar' : 'Reproducir',
                                    onPressed: c.ocupado || (!c.hayActual && c.pendientes.isEmpty) ? null : c.alternar,
                                    icon: Icon(c.sonando ? Icons.pause : Icons.play_arrow),
                                ),
                                IconButton(
                                    tooltip: 'Saltar',
                                    onPressed: c.ocupado || !c.hayActual ? null : c.saltar,
                                    icon: const Icon(Icons.skip_next),
                                ),
                                Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                        const Icon(Icons.volume_up_outlined, color: AppColors.muted),
                                        SizedBox(width: 160, child: _Volumen(controlador: c)),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        );
    }
}

/// Volumen local (CU-25): solo cambia este dispositivo, no se guarda en el servidor.
class _Volumen extends StatefulWidget {
    const _Volumen({required this.controlador});

    final ControladorMiCola controlador;

    @override
    State<_Volumen> createState() => _VolumenState();
}

class _VolumenState extends State<_Volumen> {
    double _valor = 1;

    @override
    Widget build(BuildContext context) {
        return Slider(
            value: _valor,
            onChanged: (v) {
                setState(() => _valor = v);
                widget.controlador.volumen(v);
            },
        );
    }
}

class _Pendiente extends StatelessWidget {
    const _Pendiente({
        required this.controlador,
        required this.elemento,
        required this.posicion,
        required this.total,
        required this.onRetirar,
    });

    final ControladorMiCola controlador;
    final ElementoCola elemento;
    final int posicion;
    final int total;
    final VoidCallback onRetirar;

    @override
    Widget build(BuildContext context) {
        final detalle = controlador.detalleDe(elemento.recursoAudioId);
        final libre = !controlador.ocupado;
        return ListTile(
            contentPadding: EdgeInsets.zero,
            leading: CircleAvatar(child: Text(posicion.toString().padLeft(2, '0'))),
            title: Text(detalle?.tituloConVariante ?? 'Canción'),
            subtitle: Text(detalle?.nombreArtistas ?? '', style: const TextStyle(color: AppColors.muted)),
            trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                    if (detalle != null)
                        Text(formatearDuracion(Duration(milliseconds: detalle.duracionMs)),
                             style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                    IconButton(
                        tooltip: 'Subir',
                        onPressed: libre && posicion > 1 ? () => controlador.mover(elemento.id, posicion - 1) : null,
                        icon: const Icon(Icons.arrow_upward, size: 18),
                    ),
                    IconButton(
                        tooltip: 'Bajar',
                        onPressed: libre && posicion < total ? () => controlador.mover(elemento.id, posicion + 1) : null,
                        icon: const Icon(Icons.arrow_downward, size: 18),
                    ),
                    IconButton(
                        tooltip: 'Quitar',
                        onPressed: libre ? onRetirar : null,
                        icon: const Icon(Icons.delete_outline, size: 18),
                    ),
                ],
            ),
        );
    }
}
