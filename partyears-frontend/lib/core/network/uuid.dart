import 'dart:math';

final _azar = Random.secure();

String nuevoUuid() {
    final b = List<int>.generate(16, (_) => _azar.nextInt(256));
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    final h = b.map((x) => x.toRadixString(16).padLeft(2, '0')).toList();
    
    return '${h.sublist(0, 4).join()}-${h.sublist(4, 6).join()}-''${h.sublist(6, 8).join()}-${h.sublist(8, 10).join()}-''${h.sublist(10).join()}';
}