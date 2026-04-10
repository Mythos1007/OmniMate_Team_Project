import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    default_display = os.environ.get('DISPLAY', ':1')
    default_xauthority = os.environ.get('XAUTHORITY', '')
    default_qt_platform = os.environ.get('QT_QPA_PLATFORM', 'xcb')
    default_secrets_file = os.environ.get(
        'ASSISTANT_SECRETS_FILE',
        os.path.expanduser('~/.config/assistant/secrets.json'),
    )
    default_named_places_file = os.path.join(
        FindPackageShare('assistant_bringup').find('assistant_bringup'),
        'config',
        'named_places_catalog.yaml',
    )
    audio_params = LaunchConfiguration('audio_params')
    brain_params = LaunchConfiguration('brain_params')
    ros_domain_id = LaunchConfiguration('ros_domain_id')
    ros_localhost_only = LaunchConfiguration('ros_localhost_only')
    rmw_implementation = LaunchConfiguration('rmw_implementation')
    cyclonedds_uri = LaunchConfiguration('cyclonedds_uri')
    assistant_enable_ros_bridge = LaunchConfiguration('assistant_enable_ros_bridge')

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
            DeclareLaunchArgument('ros_localhost_only', default_value='1'),
            DeclareLaunchArgument('rmw_implementation', default_value='rmw_fastrtps_cpp'),
            DeclareLaunchArgument('cyclonedds_uri', default_value=''),
            DeclareLaunchArgument('assistant_enable_ros_bridge', default_value='1'),
            SetEnvironmentVariable(name='ROS_DOMAIN_ID', value=ros_domain_id),
            SetEnvironmentVariable(name='ROS_LOCALHOST_ONLY', value=ros_localhost_only),
            SetEnvironmentVariable(name='RMW_IMPLEMENTATION', value=rmw_implementation),
            SetEnvironmentVariable(name='CYCLONEDDS_URI', value=cyclonedds_uri),
            SetEnvironmentVariable(name='ASSISTANT_ENABLE_ROS_BRIDGE', value=assistant_enable_ros_bridge),
            SetEnvironmentVariable(name='ASSISTANT_FACE_VOICE_LOOP', value='0'),
            SetEnvironmentVariable(name='ASSISTANT_NAMED_PLACES_FILE', value=default_named_places_file),
            SetEnvironmentVariable(name='DISPLAY', value=default_display),
            SetEnvironmentVariable(name='XAUTHORITY', value=default_xauthority),
            SetEnvironmentVariable(name='QT_QPA_PLATFORM', value=default_qt_platform),
            SetEnvironmentVariable(name='ASSISTANT_SECRETS_FILE', value=default_secrets_file),
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
                executable='omni_orchestrator_node',
                name='omni_orchestrator_node',
                output='screen',
            ),
            Node(
                package='assistant_gui',
                executable='assistant_gui_node',
                name='assistant_gui_node',
                output='screen',
            ),
        ]
    )
