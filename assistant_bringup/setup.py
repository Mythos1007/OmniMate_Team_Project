from glob import glob
from setuptools import find_packages, setup


package_name = 'assistant_bringup'


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='mythos',
    maintainer_email='todo@example.com',
    description='Bringup package for the assistant robot.',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'live_voice_stub_cli = assistant_bringup.tools.live_voice_stub_cli:main',
        ],
    },
)
