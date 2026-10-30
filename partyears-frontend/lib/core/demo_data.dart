import 'package:flutter/material.dart';

class Song {
  const Song({
    required this.title,
    required this.artist,
    required this.duration,
    required this.genre,
    required this.color,
  });

  final String title;
  final String artist;
  final String duration;
  final String genre;
  final Color color;
}

const demoSongs = [
  Song(
    title: 'Midnight City',
    artist: 'M83',
    duration: '4:03',
    genre: 'Electrónica',
    color: Color(0xFF8B5CF6),
  ),
  Song(
    title: 'Blinding Lights',
    artist: 'The Weeknd',
    duration: '3:20',
    genre: 'Pop',
    color: Color(0xFFE0608A),
  ),
  Song(
    title: 'After Dark',
    artist: 'Mr.Kitty',
    duration: '4:17',
    genre: 'Electrónica',
    color: Color(0xFF3B82C4),
  ),
  Song(
    title: 'Something About Us',
    artist: 'Daft Punk',
    duration: '3:51',
    genre: 'Electrónica',
    color: Color(0xFF6B9A9E),
  ),
  Song(
    title: 'Electric Feel',
    artist: 'MGMT',
    duration: '3:49',
    genre: 'Indie',
    color: Color(0xFFC0606A),
  ),
  Song(
    title: 'The Less I Know The Better',
    artist: 'Tame Impala',
    duration: '3:36',
    genre: 'Alternativa',
    color: Color(0xFFD08A3A),
  ),
];

const demoUserName = 'tresdese';
const demoUserInitials = 'TD';
const demoPartyCode = 'A7X2Q9';
const demoParticipants = 4;
const demoQueueCount = 4;
const demoVoiceMembers = 3;
