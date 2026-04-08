from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description() -> LaunchDescription:
    bringup_share = get_package_share_directory('assistant_bringup')
    distributed_launch = os.path.join(bringup_share, 'launch', 'assistant_distributed.launch.py')

    machine_role = LaunchConfiguration('machine_role')
    ros_domain_id = LaunchConfiguration('ros_domain_id')
    ros_static_peers = LaunchConfiguration('ros_static_peers')
    map_file = LaunchConfiguration('map')
    nav2_params_file = LaunchConfiguration('nav2_params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    enable_rviz = LaunchConfiguration('enable_rviz')

    return LaunchDescription(
        [
            DeclareLaunchArgument('machine_role', default_value='pc'),
            DeclareLaunchArgument('ros_domain_id', default_value='142'),
            DeclareLaunchArgument('ros_static_peers', default_value=''),
            DeclareLaunchArgument('map', default_value=''),
            DeclareLaunchArgument('nav2_params_file', default_value=''),
            DeclareLaunchArgument('use_sim_time', default_value='false'),
            DeclareLaunchArgument('enable_rviz', default_value='false'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(distributed_launch),
                launch_arguments={
                    'machine_role': machine_role,
                    'ros_domain_id': ros_domain_id,
                    'ros_localhost_only': '0',
                    'rmw_implementation': 'rmw_fastrtps_cpp',
                    'ros_automatic_discovery_range': 'SUBNET',
                    'ros_static_peers': ros_static_peers,
                    'use_sim_time': use_sim_time,
                    'enable_nav2': 'true',
                    'map': map_file,
                    'nav2_params_file': nav2_params_file,
                    'nav2_autostart': 'true',
                    'enable_rviz': enable_rviz,
                    'enable_pc_audio': 'false',
                    'enable_robot_audio': 'true',
                    'enable_gui': 'true',
                    'enable_intent_debug': 'false',
                    'enable_turtlebot_base': 'true',
                    'enable_cmd_vel_adapter': 'true',
                    'assistant_enable_ros_bridge': '1',
                    'assistant_face_voice_loop': '1',
                    'assistant_voice_only_face_mode': '1',
                }.items(),
            ),
        ]
    )
