from setuptools import find_packages, setup


package_name = 'assistant_gui'


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'requests', 'SpeechRecognition'],
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
