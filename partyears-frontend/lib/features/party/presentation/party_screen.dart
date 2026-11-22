import 'package:flutter/material.dart';

import '../../../core/network/api_exception.dart';
import '../../../core/widgets/common.dart';
import '../../queue/presentation/queue_screen.dart';
import '../../voice/presentation/voice_screen.dart';
import '../data/party_models.dart';
import 'party_en_curso.dart';

class PartyScreen extends StatefulWidget {
    const PartyScreen({
        super.key,
        required this.partyCode,
        required this.onCreate,
        required this.onLeave,
        this.party,
        this.onJoin,
    });

    final String? partyCode;

    /// La party completa cuando el usuario está dentro; sin ella solo se muestra el código.
    final PartyActual? party;
    final Future<void> Function(String codigo, {String? clave})? onJoin;

    final Future<void> Function(String nombre, {String? clave}) onCreate;
    final VoidCallback onLeave;

    @override
    State<PartyScreen> createState() => _PartyScreenState();
}

class _PartyScreenState extends State<PartyScreen> {
    static final _codeFormat = RegExp(r'^[A-Z0-9]{6}$');

    final _codeController = TextEditingController();
    final _nombreController = TextEditingController();

    bool _creando = false;
    String? _error;

    String? _claveReintento;
    String? _nombreReintento;

    bool _uniendose = false;
    String? _claveUnirse;
    String? _codigoReintento;

    @override
    void dispose() {
        _codeController.dispose();
        _nombreController.dispose();
        super.dispose();
    }

    void _showMessage(String message) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
    }

    Future<void> _join() async {
        final code = _codeController.text.trim().toUpperCase();
        final onJoin = widget.onJoin;

        if (!_codeFormat.hasMatch(code)) {
            _showMessage('Ingresa un código válido de seis caracteres');
            return;
        }
        if (onJoin == null) {
            _showMessage('Unirse requiere el backend');
            return;
        }

        setState(() => _uniendose = true);
        // Same key on a retry after a network failure (contract 1.6), like creating a party.
        final clave = code == _codigoReintento ? _claveUnirse : null;

        try {
            await onJoin(code, clave: clave);
            _claveUnirse = null;
            _codigoReintento = null;
        } on ApiException catch (e) {
            if (!mounted) return;
            _claveUnirse = e.esDeRed ? e.idempotencyKey : null;
            _codigoReintento = e.esDeRed ? code : null;
            _showMessage(e.mensaje);
        } finally {
            if (mounted) setState(() => _uniendose = false);
        }
    }

    Future<void> _crear() async {
        final nombre = _nombreController.text.trim();

        if (nombre.isEmpty) {
            setState(() => _error = 'Ponle un nombre a la party.');
            
            return;
        }

        setState(() {
            _creando = true;
            _error = null;
        });

        final clave = nombre == _nombreReintento ? _claveReintento : null;

        try {
            await widget.onCreate(nombre, clave: clave);
            _claveReintento = null;
            _nombreReintento = null;
        } on ApiException catch (e) {
            if (!mounted) return;

            setState(() {
                _error = e.mensaje;
                _claveReintento = e.esDeRed ? e.idempotencyKey : null;
                _nombreReintento = e.esDeRed ? nombre : null;
            });
        } finally {
            if (mounted) setState(() => _creando = false);
        }
    }

    @override
    Widget build(BuildContext context) {
        final party = widget.party;
        if (party != null) {
            return PartyEnCurso(key: ValueKey(party.id), party: party, onLeave: widget.onLeave);
        }

        final code = widget.partyCode;

        return ListView(
            padding: const EdgeInsets.all(24),
            children: code == null ? _noParty() : _inParty(code),
        );
    }

    List<Widget> _noParty() => [
        Text('Tus parties', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 16),
        TextField(
            controller: _nombreController, 
            maxLength: 100, 
            enabled: !_creando, 
            decoration: const InputDecoration(
                labelText: 'Nombre de la party', 
                hintText: 'Fiesta del sábado',
            ), 
            onSubmitted: (_) => _crear(),
        ),
        if (_error != null)
        Padding(
            padding: const EdgeInsets.only(bottom: 8), 
            child: Text(
                _error!, 
                style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
        ),
        FilledButton.icon(
            onPressed: _creando ? null : _crear, 
            icon: _creando ? const SizedBox(
                width: 18, 
                height: 18, 
                child: CircularProgressIndicator(strokeWidth: 2),
            ) : const Icon(Icons.add), 
            label: const Text('Crear Party'),
        ),
        const SizedBox(height: 12),
        TextField(
            controller: _codeController, 
            maxLength: 6, 
            textCapitalization: TextCapitalization.characters,
            decoration: const InputDecoration(
                labelText: 'Código de invitación', 
                hintText: 'ABC123',
            ), 
            onSubmitted: (_) => _join(),
        ),
        OutlinedButton(
            onPressed: _uniendose ? null : _join,
            child: const Text('Unirse a una Party'),
        ),
    ];

    List<Widget> _inParty(String code) => [
        Text('Tu party', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 16),
        ListTile(
            leading: const Icon(Icons.vpn_key_outlined),
            title: const Text('Código de invitación'),
            subtitle: Text(code),
            trailing: IconButton(
                tooltip: 'Copiar código',
                onPressed: () => copyPartyCode(context, code),
                icon: const Icon(Icons.copy_outlined),
            ),
        ),
        ListTile(
            leading: const Icon(Icons.queue_music),
            title: const Text('Cola de reproducción'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(builder: (_) => const QueueScreen()),
            ),
        ),
        ListTile(
            leading: const Icon(Icons.mic_none),
            title: const Text('Sala de voz'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(builder: (_) => const VoiceScreen()),
            ),
        ),
        const Divider(height: 40),
            OutlinedButton.icon(
            onPressed: widget.onLeave,
            icon: const Icon(Icons.exit_to_app),
            label: const Text('Salir de la party (demo)'),
        ),
    ];
}