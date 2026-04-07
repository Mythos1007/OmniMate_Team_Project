from setuptools import find_packages, setup


package_name = 'assistant_commands'


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
    description='Canonical voice command pipeline for the assistant robot.',
    license='TODO',
    tests_require=['pytest'],
)
