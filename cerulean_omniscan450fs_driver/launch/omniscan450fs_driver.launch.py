import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('cerulean_omniscan450fs_driver'),
        'config',
        'omniscan450fs_driver.yaml'
    )

    return LaunchDescription([
        Node(
            package='cerulean_omniscan450fs_driver',
            executable='omniscan450fs_driver',
            name='omniscan450fs_driver',
            output='screen',
            parameters=[config]
        )
    ])
