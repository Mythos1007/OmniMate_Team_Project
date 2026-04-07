from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    audio_params = LaunchConfiguration('audio_params')
    enable_tts = LaunchConfiguration('enable_tts')
    tts_backend = LaunchConfiguration('tts_backend')
    voice_name = LaunchConfiguration('voice_name')
    language = LaunchConfiguration('language')
    fallback_voice_name = LaunchConfiguration('fallback_voice_name')
    playback_command = LaunchConfiguration('playback_command')
    elevenlabs_api_key = LaunchConfiguration('elevenlabs_api_key')
    elevenlabs_voice_id = LaunchConfiguration('elevenlabs_voice_id')
    elevenlabs_model_id = LaunchConfiguration('elevenlabs_model_id')
    elevenlabs_output_format = LaunchConfiguration('elevenlabs_output_format')
    cartesia_api_key = LaunchConfiguration('cartesia_api_key')
    cartesia_voice_id = LaunchConfiguration('cartesia_voice_id')
    cartesia_model_id = LaunchConfiguration('cartesia_model_id')
    cartesia_output_container = LaunchConfiguration('cartesia_output_container')
    cartesia_output_encoding = LaunchConfiguration('cartesia_output_encoding')
    cartesia_sample_rate = LaunchConfiguration('cartesia_sample_rate')

    default_audio_params = PathJoinSubstitution(
        [FindPackageShare('assistant_bringup'), 'config', 'assistant_audio.yaml']
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument('audio_params', default_value=default_audio_params),
            DeclareLaunchArgument('enable_tts', default_value='true'),
            DeclareLaunchArgument('tts_backend', default_value='edge_tts'),
            DeclareLaunchArgument('voice_name', default_value='ko-KR-SunHiNeural'),
            DeclareLaunchArgument('language', default_value='ko'),
            DeclareLaunchArgument('fallback_voice_name', default_value='female1'),
            DeclareLaunchArgument('playback_command', default_value='gst-play-1.0'),
            DeclareLaunchArgument('elevenlabs_api_key', default_value=''),
            DeclareLaunchArgument('elevenlabs_voice_id', default_value=''),
            DeclareLaunchArgument('elevenlabs_model_id', default_value='eleven_multilingual_v2'),
            DeclareLaunchArgument('elevenlabs_output_format', default_value='mp3_44100_128'),
            DeclareLaunchArgument('cartesia_api_key', default_value=''),
            DeclareLaunchArgument('cartesia_voice_id', default_value=''),
            DeclareLaunchArgument('cartesia_model_id', default_value='sonic-3'),
            DeclareLaunchArgument('cartesia_output_container', default_value='wav'),
            DeclareLaunchArgument('cartesia_output_encoding', default_value='pcm_f32le'),
            DeclareLaunchArgument('cartesia_sample_rate', default_value='44100'),
            LogInfo(msg=['[assistant_robot_tts] enable_tts=', enable_tts]),
            LogInfo(
                msg=[
                    '[assistant_robot_tts] TTS backend=',
                    tts_backend,
                    ', voice_name=',
                    voice_name,
                    ', language=',
                    language,
                    ', fallback_voice_name=',
                    fallback_voice_name,
                    ', playback_command=',
                    playback_command,
                    ', elevenlabs_voice_id=',
                    elevenlabs_voice_id,
                    ', elevenlabs_model_id=',
                    elevenlabs_model_id,
                    ', cartesia_voice_id=',
                    cartesia_voice_id,
                    ', cartesia_model_id=',
                    cartesia_model_id,
                ]
            ),
            # NOTE:
            # STT emits /assistant/transcript, while tts_node subscribes to /assistant/speak.
            # A transcript->speak bridge node or assistant orchestration logic is required
            # for automatic spoken responses.
            Node(
                package='assistant_audio',
                executable='tts_node',
                name='tts_node',
                output='screen',
                condition=IfCondition(enable_tts),
                parameters=[
                    audio_params,
                    {
                        'tts_backend': tts_backend,
                        'voice_name': voice_name,
                        'language': language,
                        'fallback_voice_name': fallback_voice_name,
                        'playback_command': playback_command,
                        'elevenlabs_api_key': elevenlabs_api_key,
                        'elevenlabs_voice_id': elevenlabs_voice_id,
                        'elevenlabs_model_id': elevenlabs_model_id,
                        'elevenlabs_output_format': elevenlabs_output_format,
                        'cartesia_api_key': cartesia_api_key,
                        'cartesia_voice_id': cartesia_voice_id,
                        'cartesia_model_id': cartesia_model_id,
                        'cartesia_output_container': cartesia_output_container,
                        'cartesia_output_encoding': cartesia_output_encoding,
                        'cartesia_sample_rate': cartesia_sample_rate,
                    },
                ],
            ),
        ]
    )
