from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    audio_params = LaunchConfiguration('audio_params')
    brain_params = LaunchConfiguration('brain_params')
    ros_domain_id = LaunchConfiguration('ros_domain_id')
    ros_localhost_only = LaunchConfiguration('ros_localhost_only')
    rmw_implementation = LaunchConfiguration('rmw_implementation')
    cyclonedds_uri = LaunchConfiguration('cyclonedds_uri')

    default_audio_params = PathJoinSubstitution(
        [FindPackageShare('assistant_bringup'), 'config', 'assistant_audio.yaml']
    )
    default_brain_params = PathJoinSubstitution(
        [FindPackageShare('assistant_bringup'), 'config', 'assistant_brain.yaml']
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument('audio_params', default_value=default_audio_params),
            DeclareLaunchArgument('brain_params', default_value=default_brain_params),
            DeclareLaunchArgument('ros_domain_id', default_value='142'),
            DeclareLaunchArgument('ros_localhost_only', default_value='0'),
            DeclareLaunchArgument('rmw_implementation', default_value='rmw_cyclonedds_cpp'),
            DeclareLaunchArgument('cyclonedds_uri', default_value=''),
            SetEnvironmentVariable(name='ROS_DOMAIN_ID', value=ros_domain_id),
            SetEnvironmentVariable(name='ROS_LOCALHOST_ONLY', value=ros_localhost_only),
            SetEnvironmentVariable(name='RMW_IMPLEMENTATION', value=rmw_implementation),
            SetEnvironmentVariable(name='CYCLONEDDS_URI', value=cyclonedds_uri),
            Node(
                package='assistant_audio',
                executable='stt_node',
                name='stt_node',
                output='screen',
                parameters=[audio_params],
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
                package='assistant_gui',
                executable='assistant_gui_node',
                name='assistant_gui_node',
                output='screen',
            ),
        ]
    )
