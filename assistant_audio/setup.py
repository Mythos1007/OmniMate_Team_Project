from setuptools import find_packages, setup


package_name = 'assistant_audio'


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'edge-tts', 'faster-whisper', 'requests'],
    zip_safe=True,
    maintainer='mythos',
    maintainer_email='todo@example.com',
    description='Audio stack for the assistant robot project.',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'wake_word_node = assistant_audio.wake_word_node:main',
            'stt_node = assistant_audio.stt_node:main',
            'tts_node = assistant_audio.tts_node:main',
            'tts_smoke_test = assistant_audio.tools.tts_smoke_test:main',
            'mic_stt_test = assistant_audio.tools.mic_stt_test:main',
            'mic_echo_test = assistant_audio.tools.mic_echo_test:main',
            'command_pipeline_cli = assistant_audio.tools.command_pipeline_cli:main',
        ],
    },
)
