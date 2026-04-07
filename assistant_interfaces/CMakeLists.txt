cmake_minimum_required(VERSION 3.8)
project(assistant_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(action_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

set(msg_files
  "msg/VoiceTranscript.msg"
  "msg/AssistantIntent.msg"
  "msg/AssistantState.msg"
)

set(srv_files
  "srv/GetRobotStatus.srv"
)

set(action_files
  "action/GuideToNamedPlace.action"
  "action/FollowPerson.action"
  "action/PatrolOnce.action"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${msg_files}
  ${srv_files}
  ${action_files}
  DEPENDENCIES builtin_interfaces action_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
