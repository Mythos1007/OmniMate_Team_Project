from glob import glob
from pathlib import Path

from setuptools import find_packages, setup


package_name = 'assistant_gui'


def _package_data_files() -> list[str]:
    patterns = [
        'assets/faces/*.svg',
        'icons/*.svg',
        '*.json',
        '*.yaml',
        '*.pgm',
        '*.png',
    ]
    collected: list[str] = []
    package_root = Path(package_name)
    for pattern in patterns:
        for path_str in glob(str(package_root / pattern)):
            path = Path(path_str)
            collected.append(path.relative_to(package_root).as_posix())
    return sorted(set(collected))


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    package_data={package_name: _package_data_files()},
    include_package_data=True,
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'requests', 'SpeechRecognition', 'PyYAML'],
    zip_safe=True,
    maintainer='mythos',
    maintainer_email='todo@example.com',
    description='GUI package for the assistant robot.',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'assistant_gui_node = assistant_gui.main:main',
            'assistant_gui_face_demo = assistant_gui.face.face_demo:main',
        ],
    },
)
