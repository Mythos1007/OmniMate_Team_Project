from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.substitutions import PathJoinSubstitution
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    audio_params = LaunchConfiguration('audio_params')
    brain_params = LaunchConfiguration('brain_params')
    robot_params = LaunchConfiguration('robot_params')
    named_places_params = LaunchConfiguration('named_places_params')
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
    default_audio_params = PathJoinSubstitution(
        [FindPackageShare('assistant_bringup'), 'config', 'assistant_audio.yaml']
    )
    default_brain_params = PathJoinSubstitution(
        [FindPackageShare('assistant_bringup'), 'config', 'assistant_brain.yaml']
    )
    default_robot_params = PathJoinSubstitution(
        [FindPackageShare('assistant_bringup'), 'config', 'assistant_robot.yaml']
    )
    default_named_places_params = PathJoinSubstitution(
        [FindPackageShare('assistant_bringup'), 'config', 'named_places.yaml']
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'audio_params',
                default_value=default_audio_params,
            ),
            DeclareLaunchArgument(
                'brain_params',
                default_value=default_brain_params,
            ),
            DeclareLaunchArgument(
                'robot_params',
                default_value=default_robot_params,
            ),
            DeclareLaunchArgument(
                'named_places_params',
                default_value=default_named_places_params,
            ),
            DeclareLaunchArgument(
                'ros_domain_id',
                default_value='142',
            ),
            DeclareLaunchArgument(
                'ros_localhost_only',
                default_value='0',
            ),
            DeclareLaunchArgument(
                'rmw_implementation',
                default_value='rmw_cyclonedds_cpp',
            ),
            DeclareLaunchArgument(
                'cyclonedds_uri',
                default_value='',
            ),
            DeclareLaunchArgument(
                'enable_tts',
                default_value='true',
            ),
            DeclareLaunchArgument(
                'tts_backend',
                default_value='edge_tts',
            ),
            DeclareLaunchArgument(
                'voice_name',
                default_value='ko-KR-SunHiNeural',
            ),
            DeclareLaunchArgument(
                'language',
                default_value='ko',
            ),
            DeclareLaunchArgument(
                'fallback_voice_name',
                default_value='female1',
            ),
            DeclareLaunchArgument(
                'playback_command',
                default_value='gst-play-1.0',
            ),
            DeclareLaunchArgument(
                'elevenlabs_api_key',
                default_value='',
            ),
            DeclareLaunchArgument(
                'elevenlabs_voice_id',
                default_value='',
            ),
            DeclareLaunchArgument(
                'elevenlabs_model_id',
                default_value='eleven_multilingual_v2',
            ),
            DeclareLaunchArgument(
                'elevenlabs_output_format',
                default_value='mp3_44100_128',
            ),
            DeclareLaunchArgument(
                'cartesia_api_key',
                default_value='',
            ),
            DeclareLaunchArgument(
                'cartesia_voice_id',
                default_value='',
            ),
            DeclareLaunchArgument(
                'cartesia_model_id',
                default_value='sonic-3',
            ),
            DeclareLaunchArgument(
                'cartesia_output_container',
                default_value='wav',
            ),
            DeclareLaunchArgument(
                'cartesia_output_encoding',
                default_value='pcm_f32le',
            ),
            DeclareLaunchArgument(
                'cartesia_sample_rate',
                default_value='44100',
            ),
            SetEnvironmentVariable(name='ROS_DOMAIN_ID', value=ros_domain_id),
            SetEnvironmentVariable(name='ROS_LOCALHOST_ONLY', value=ros_localhost_only),
            SetEnvironmentVariable(name='RMW_IMPLEMENTATION', value=rmw_implementation),
            SetEnvironmentVariable(name='CYCLONEDDS_URI', value=cyclonedds_uri),
            LogInfo(msg=['[assistant_core] enable_tts=', enable_tts]),
            LogInfo(
                msg=[
                    '[assistant_core] TTS backend=',
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
            Node(
                package='assistant_audio',
                executable='wake_word_node',
                name='wake_word_node',
                output='screen',
                parameters=[audio_params],
            ),
            Node(
                package='assistant_audio',
                executable='stt_node',
                name='stt_node',
                output='screen',
                parameters=[audio_params],
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
            Node(
                package='assistant_brain',
                executable='dialog_manager_node',
                name='dialog_manager_node',
                output='screen',
                parameters=[brain_params],
            ),
            Node(
                package='assistant_brain',
                executable='intent_router_node',
                name='intent_router_node',
                output='screen',
                parameters=[brain_params],
            ),
            Node(
                package='assistant_robot',
                executable='task_manager_node',
                name='task_manager_node',
                output='screen',
                parameters=[robot_params],
            ),
            Node(
                package='assistant_robot',
                executable='nav_bridge_node',
                name='nav_bridge_node',
                output='screen',
                parameters=[robot_params, named_places_params],
            ),
            Node(
                package='assistant_robot',
                executable='cmd_vel_adapter_node',
                name='cmd_vel_adapter_node',
                output='screen',
                parameters=[robot_params],
            ),
            Node(
                package='assistant_robot',
                executable='safety_gate_node',
                name='safety_gate_node',
                output='screen',
                parameters=[robot_params],
            ),
            Node(
                package='assistant_robot',
                executable='status_provider_node',
                name='status_provider_node',
                output='screen',
                parameters=[robot_params],
            ),
            Node(
                package='assistant_gui',
                executable='assistant_gui_node',
                name='assistant_gui_node',
                output='screen',
            ),
        ]
    )
