from setuptools import find_packages, setup


package_name = 'assistant_robot'


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    package_data={
        'assistant_robot.config': ['*.yaml'],
        'assistant_robot.resources': ['*.yaml'],
    },
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'PyYAML'],
    zip_safe=True,
    maintainer='mythos',
    maintainer_email='todo@example.com',
    description='Robot-side orchestration package for the assistant robot.',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'task_manager_node = assistant_robot.task_manager_node:main',
            'nav_bridge_node = assistant_robot.nav_bridge_node:main',
            'cmd_vel_adapter_node = assistant_robot.cmd_vel_adapter_node:main',
            'safety_gate_node = assistant_robot.safety_gate_node:main',
            'status_provider_node = assistant_robot.status_provider_node:main',
            'omni_orchestrator_node = assistant_robot.orchestrator.orchestrator_node:main',
            'wakeword_node = assistant_robot.nodes.wakeword_node:main',
            'stt_node = assistant_robot.nodes.stt_node:main',
            'intent_parser_node = assistant_robot.nodes.intent_parser_node:main',
            'scheduler_node = assistant_robot.nodes.scheduler_node:main',
            'gui_bridge_node = assistant_robot.nodes.gui_bridge_node:main',
            'battery_monitor_node = assistant_robot.nodes.battery_monitor_node:main',
            'person_recognition_node = assistant_robot.nodes.person_recognition_node:main',
            'assistant_robot_demo = assistant_robot.demo:main',
        ],
    },
)
