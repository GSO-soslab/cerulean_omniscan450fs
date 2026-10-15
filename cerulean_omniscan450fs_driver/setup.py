from setuptools import find_packages, setup

package_name = 'cerulean_omniscan450fs_driver'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', ['config/omniscan450fs_driver.yaml']),
        ('share/' + package_name + '/launch', ['launch/omniscan450fs_driver.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Farhang Naderi',
    maintainer_email='farhang.naderi@uri.edu',
    description='ROS 2 driver for the Cerulean Omniscan 450 FS forward-scan sonar',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'omniscan450fs_driver = cerulean_omniscan450fs_driver.omniscan450fs_node:main',
            'fake_sonar = cerulean_omniscan450fs_driver.fake_sonar:main',
        ],
    },
)
