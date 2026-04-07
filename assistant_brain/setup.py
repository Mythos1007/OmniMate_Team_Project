from setuptools import find_packages, setup


package_name = 'assistant_brain'


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='mythos',
    maintainer_email='todo@example.com',
    description='Assistant dialog and intent orchestration package.',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'dialog_manager_node = assistant_brain.dialog_manager_node:main',
            'intent_router_node = assistant_brain.intent_router_node:main',
            'stub_demo_cli = assistant_brain.tools.stub_demo_cli:main',
        ],
    },
)
