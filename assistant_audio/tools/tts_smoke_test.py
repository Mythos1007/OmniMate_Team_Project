from __future__ import annotations

import argparse

from assistant_audio.providers.tts_provider import (
    CartesiaTTSProvider,
    EdgeTTSProvider,
    ElevenLabsTTSProvider,
    MockTTSProvider,
    SpeechDispatcherTTSProvider,
    TTSProvider,
)


def _build_provider(args: argparse.Namespace) -> TTSProvider:
    backend = args.backend.strip().lower()

    if backend == 'speech_dispatcher':
        return SpeechDispatcherTTSProvider(
            voice_name=args.voice_name,
            language=args.language,
        )

    if backend == 'edge_tts':
        fallback = SpeechDispatcherTTSProvider(
            voice_name=args.fallback_voice_name,
            language='',
        )
        return EdgeTTSProvider(
            voice_name=args.voice_name,
            playback_command=args.playback_command,
            fallback_provider=fallback,
        )

    if backend == 'elevenlabs':
        fallback = SpeechDispatcherTTSProvider(
            voice_name=args.fallback_voice_name,
            language='',
        )
        return ElevenLabsTTSProvider(
            api_key=args.elevenlabs_api_key,
            voice_id=args.elevenlabs_voice_id,
            model_id=args.elevenlabs_model_id,
            playback_command=args.playback_command,
            output_format=args.elevenlabs_output_format,
            fallback_provider=fallback,
        )

    if backend == 'cartesia':
        fallback = SpeechDispatcherTTSProvider(
            voice_name=args.fallback_voice_name,
            language='',
        )
        return CartesiaTTSProvider(
            api_key=args.cartesia_api_key,
            voice_id=args.cartesia_voice_id,
            model_id=args.cartesia_model_id,
            playback_command=args.playback_command,
            output_container=args.cartesia_output_container,
            output_encoding=args.cartesia_output_encoding,
            sample_rate=args.cartesia_sample_rate,
            fallback_provider=fallback,
        )

    return MockTTSProvider(lambda text: print(f'[MockTTS] {text}'))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run a direct TTS smoke test without ROS topic communication.',
    )
    parser.add_argument(
        '--backend',
        default='speech_dispatcher',
        choices=['speech_dispatcher', 'edge_tts', 'elevenlabs', 'cartesia', 'mock'],
    )
    parser.add_argument('--text', default='TTS smoke test from assistant_audio')
    parser.add_argument('--voice-name', default='female1')
    parser.add_argument('--language', default='')
    parser.add_argument('--fallback-voice-name', default='female1')
    parser.add_argument('--playback-command', default='gst-play-1.0')
    parser.add_argument('--elevenlabs-api-key', default='')
    parser.add_argument('--elevenlabs-voice-id', default='')
    parser.add_argument('--elevenlabs-model-id', default='eleven_multilingual_v2')
    parser.add_argument('--elevenlabs-output-format', default='mp3_44100_128')
    parser.add_argument('--cartesia-api-key', default='')
    parser.add_argument('--cartesia-voice-id', default='')
    parser.add_argument('--cartesia-model-id', default='sonic-3')
    parser.add_argument('--cartesia-output-container', default='wav')
    parser.add_argument('--cartesia-output-encoding', default='pcm_f32le')
    parser.add_argument('--cartesia-sample-rate', type=int, default=44100)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    provider = _build_provider(args)

    print(
        f"[INFO] backend={args.backend}, voice={args.voice_name}, language='{args.language}', "
        f"elevenlabs_voice_id={args.elevenlabs_voice_id}, elevenlabs_model_id={args.elevenlabs_model_id}, "
        f"cartesia_voice_id={args.cartesia_voice_id}, cartesia_model_id={args.cartesia_model_id}"
    )
    print(f"[INFO] speaking: {args.text}")

    try:
        provider.speak(args.text)
        print('[OK] TTS request executed. If audio path is healthy, you should hear sound.')
    except Exception as exc:  # pragma: no cover - runtime diagnostics path
        print(f'[ERROR] TTS smoke test failed: {exc}')
        raise SystemExit(1) from exc


if __name__ == '__main__':
    main()
