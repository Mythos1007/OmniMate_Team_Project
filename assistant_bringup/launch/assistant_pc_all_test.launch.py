from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    ros_domain_id = LaunchConfiguration('ros_domain_id')
    ros_localhost_only = LaunchConfiguration('ros_localhost_only')
    rmw_implementation = LaunchConfiguration('rmw_implementation')
    cyclonedds_uri = LaunchConfiguration('cyclonedds_uri')
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

    core_launch = PathJoinSubstitution(
        [FindPackageShare('assistant_bringup'), 'launch', 'assistant_core.launch.py']
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument('ros_domain_id', default_value='142'),
            DeclareLaunchArgument('ros_localhost_only', default_value='0'),
            DeclareLaunchArgument('rmw_implementation', default_value='rmw_cyclonedds_cpp'),
            DeclareLaunchArgument('cyclonedds_uri', default_value=''),
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
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(core_launch),
                launch_arguments={
                    'audio_params': PathJoinSubstitution(
                        [FindPackageShare('assistant_bringup'), 'config', 'assistant_audio.yaml']
                    ),
                    'brain_params': PathJoinSubstitution(
                        [FindPackageShare('assistant_bringup'), 'config', 'assistant_brain.yaml']
                    ),
                    'robot_params': PathJoinSubstitution(
                        [FindPackageShare('assistant_bringup'), 'config', 'assistant_robot.yaml']
                    ),
                    'named_places_params': PathJoinSubstitution(
                        [FindPackageShare('assistant_bringup'), 'config', 'named_places.yaml']
                    ),
                    'ros_domain_id': ros_domain_id,
                    'ros_localhost_only': ros_localhost_only,
                    'rmw_implementation': rmw_implementation,
                    'cyclonedds_uri': cyclonedds_uri,
                    'enable_tts': enable_tts,
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
                }.items(),
            )
        ]
    )
