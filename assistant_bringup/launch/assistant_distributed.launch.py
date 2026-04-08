from __future__ import annotations

import os

from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _get_str(context, name: str) -> str:
    return LaunchConfiguration(name).perform(context).strip()


def _get_bool(context, name: str) -> bool:
    return _get_str(context, name).lower() in {"1", "true", "yes", "on"}


def _optional_include(package_name: str, launch_file: str, launch_arguments: dict[str, str] | None = None):
    try:
        share_dir = get_package_share_directory(package_name)
    except PackageNotFoundError:
        return LogInfo(msg=f"[assistant_distributed] Skipping optional launch: package '{package_name}' not found")

    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(share_dir, 'launch', launch_file)),
        launch_arguments=(launch_arguments or {}).items(),
    )


def _build_runtime(context, *args, **kwargs):
    del args, kwargs
    actions = []

    machine_role = _get_str(context, 'machine_role') or 'pc'
    run_pc = machine_role in {'pc', 'all'}
    run_robot = machine_role in {'robot', 'all'}

    audio_params = _get_str(context, 'audio_params')
    robot_params = _get_str(context, 'robot_params')
    tts_profile = _get_str(context, 'tts_profile') or 'demo'

    if run_pc:
        actions.append(LogInfo(msg='[assistant_distributed] Starting PC-side compute stack'))

        if _get_bool(context, 'enable_nav2'):
            nav2_package = _get_str(context, 'nav2_package') or 'turtlebot3_navigation2'
            nav2_launch_file = _get_str(context, 'nav2_launch_file') or 'navigation2.launch.py'
            nav2_arguments = {
                'use_sim_time': _get_str(context, 'use_sim_time') or 'false',
                'autostart': _get_str(context, 'nav2_autostart') or 'true',
            }
            map_file = _get_str(context, 'map')
            nav2_params_file = _get_str(context, 'nav2_params_file')
            if map_file:
                nav2_arguments['map'] = map_file
            if nav2_params_file:
                nav2_arguments['params_file'] = nav2_params_file
            if _get_str(context, 'enable_rviz'):
                nav2_arguments['use_rviz'] = _get_str(context, 'enable_rviz')

            actions.append(_optional_include(nav2_package, nav2_launch_file, nav2_arguments))

        if _get_bool(context, 'enable_pc_audio'):
            actions.extend(
                [
                    Node(
                        package='assistant_audio',
                        executable='wake_word_node',
                        name='wake_word_node',
                        output='screen',
                        parameters=[audio_params, {
                            'wake_topic': '/assistant/wake_detected/pc',
                            'enabled_topic': '/assistant/audio/pc/input_enabled',
                            'availability_topic': '/assistant/audio/pc/input_available',
                            'voice_input_enabled': True,
                        }],
                    ),
                    Node(
                        package='assistant_audio',
                        executable='stt_node',
                        name='stt_node',
                        output='screen',
                        parameters=[audio_params, {
                            'wake_topic': '/assistant/wake_detected/pc',
                            'command_topic': '/assistant/command_text/pc',
                            'enabled_topic': '/assistant/audio/pc/input_enabled',
                            'voice_input_enabled': True,
                        }],
                    ),
                    Node(
                        package='assistant_audio',
                        executable='tts_node',
                        name='tts_node',
                        output='screen',
                        parameters=[audio_params],
                    ),
                ]
            )

        actions.extend(
            [
                Node(
                    package='assistant_robot',
                    executable='omni_orchestrator_node',
                    name='omni_orchestrator_node',
                    output='screen',
                    parameters=[{'tts_profile': tts_profile}],
                ),
                Node(
                    package='assistant_robot',
                    executable='nav_bridge_node',
                    name='nav_bridge_node',
                    output='screen',
                ),
                Node(
                    package='assistant_robot',
                    executable='scheduler_node',
                    name='scheduler_node',
                    output='screen',
                ),
            ]
        )

        if _get_bool(context, 'enable_intent_debug'):
            actions.append(
                Node(
                    package='assistant_robot',
                    executable='intent_parser_node',
                    name='intent_parser_node',
                    output='screen',
                )
            )

        if _get_bool(context, 'enable_gui'):
            actions.append(
                Node(
                    package='assistant_gui',
                    executable='assistant_gui_node',
                    name='assistant_gui_node',
                    output='screen',
                )
            )

    if run_robot:
        actions.append(LogInfo(msg='[assistant_distributed] Starting robot-side execution/sensor stack'))

        if _get_bool(context, 'enable_robot_audio'):
            actions.extend(
                [
                    Node(
                        package='assistant_audio',
                        executable='wake_word_node',
                        name='wake_word_node',
                        output='screen',
                        parameters=[audio_params, {
                            'wake_topic': '/assistant/wake_detected/robot',
                            'enabled_topic': '/assistant/audio/robot/input_enabled',
                            'availability_topic': '/assistant/audio/robot/input_available',
                            'voice_input_enabled': True,
                        }],
                    ),
                    Node(
                        package='assistant_audio',
                        executable='stt_node',
                        name='stt_node',
                        output='screen',
                        parameters=[audio_params, {
                            'wake_topic': '/assistant/wake_detected/robot',
                            'command_topic': '/assistant/command_text/robot',
                            'enabled_topic': '/assistant/audio/robot/input_enabled',
                            'voice_input_enabled': True,
                        }],
                    ),
                    Node(
                        package='assistant_audio',
                        executable='tts_node',
                        name='tts_node',
                        output='screen',
                        parameters=[audio_params],
                    ),
                ]
            )

        if _get_bool(context, 'enable_turtlebot_base'):
            robot_package = _get_str(context, 'robot_bringup_package') or 'turtlebot3_bringup'
            robot_launch_file = _get_str(context, 'robot_launch_file') or 'robot.launch.py'
            robot_arguments = {}
            if _get_str(context, 'use_sim_time'):
                robot_arguments['use_sim_time'] = _get_str(context, 'use_sim_time')
            actions.append(_optional_include(robot_package, robot_launch_file, robot_arguments))

        if _get_bool(context, 'enable_cmd_vel_adapter'):
            actions.append(
                Node(
                    package='assistant_robot',
                    executable='cmd_vel_adapter_node',
                    name='cmd_vel_adapter_node',
                    output='screen',
                    parameters=[robot_params],
                )
            )

        if _get_bool(context, 'enable_person_recognition'):
            actions.append(
                Node(
                    package='assistant_robot',
                    executable='person_recognition_node',
                    name='person_recognition_node',
                    output='screen',
                )
            )

    if not actions:
        actions.append(LogInfo(msg='[assistant_distributed] No components selected. Check machine_role and enable_* arguments.'))
    return actions


def generate_launch_description() -> LaunchDescription:
    bringup_share = get_package_share_directory('assistant_bringup')
    default_audio_params = os.path.join(bringup_share, 'config', 'assistant_audio.yaml')
    default_robot_params = os.path.join(bringup_share, 'config', 'assistant_robot.yaml')

    return LaunchDescription(
        [
            DeclareLaunchArgument('machine_role', default_value='pc'),
            DeclareLaunchArgument('audio_params', default_value=default_audio_params),
            DeclareLaunchArgument('robot_params', default_value=default_robot_params),
            DeclareLaunchArgument('tts_profile', default_value='demo'),
            DeclareLaunchArgument('ros_domain_id', default_value='142'),
            DeclareLaunchArgument('ros_localhost_only', default_value='0'),
            DeclareLaunchArgument('rmw_implementation', default_value='rmw_fastrtps_cpp'),
            DeclareLaunchArgument('ros_automatic_discovery_range', default_value='SUBNET'),
            DeclareLaunchArgument('ros_static_peers', default_value=''),
            DeclareLaunchArgument('use_sim_time', default_value='false'),
            DeclareLaunchArgument('enable_nav2', default_value='true'),
            DeclareLaunchArgument('nav2_package', default_value='turtlebot3_navigation2'),
            DeclareLaunchArgument('nav2_launch_file', default_value='navigation2.launch.py'),
            DeclareLaunchArgument('nav2_params_file', default_value=''),
            DeclareLaunchArgument('map', default_value=''),
            DeclareLaunchArgument('nav2_autostart', default_value='true'),
            DeclareLaunchArgument('enable_rviz', default_value='false'),
            DeclareLaunchArgument('enable_pc_audio', default_value='true'),
            DeclareLaunchArgument('enable_robot_audio', default_value='false'),
            DeclareLaunchArgument('enable_gui', default_value='true'),
            DeclareLaunchArgument('enable_intent_debug', default_value='false'),
            DeclareLaunchArgument('enable_turtlebot_base', default_value='false'),
            DeclareLaunchArgument('robot_bringup_package', default_value='turtlebot3_bringup'),
            DeclareLaunchArgument('robot_launch_file', default_value='robot.launch.py'),
            DeclareLaunchArgument('enable_cmd_vel_adapter', default_value='false'),
            DeclareLaunchArgument('enable_person_recognition', default_value='true'),
            DeclareLaunchArgument('assistant_enable_ros_bridge', default_value='1'),
            DeclareLaunchArgument('assistant_face_voice_loop', default_value='0'),
            DeclareLaunchArgument('assistant_voice_only_face_mode', default_value='1'),
            SetEnvironmentVariable(name='ROS_DOMAIN_ID', value=LaunchConfiguration('ros_domain_id')),
            SetEnvironmentVariable(name='ROS_LOCALHOST_ONLY', value=LaunchConfiguration('ros_localhost_only')),
            SetEnvironmentVariable(name='RMW_IMPLEMENTATION', value=LaunchConfiguration('rmw_implementation')),
            SetEnvironmentVariable(name='ROS_AUTOMATIC_DISCOVERY_RANGE', value=LaunchConfiguration('ros_automatic_discovery_range')),
            SetEnvironmentVariable(name='ROS_STATIC_PEERS', value=LaunchConfiguration('ros_static_peers')),
            SetEnvironmentVariable(name='ASSISTANT_ENABLE_ROS_BRIDGE', value=LaunchConfiguration('assistant_enable_ros_bridge')),
            SetEnvironmentVariable(name='ASSISTANT_FACE_VOICE_LOOP', value=LaunchConfiguration('assistant_face_voice_loop')),
            SetEnvironmentVariable(name='ASSISTANT_VOICE_ONLY_FACE_MODE', value=LaunchConfiguration('assistant_voice_only_face_mode')),
            OpaqueFunction(function=_build_runtime),
        ]
    )
