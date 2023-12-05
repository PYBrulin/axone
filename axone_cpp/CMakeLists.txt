# CMakeLists.txt

cmake_minimum_required(VERSION 3.10)
project(MyProject)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED True)

include_directories(${CMAKE_CURRENT_SOURCE_DIR}) # Add this line if json.h is in the same directory as CMakeLists.txt

add_executable(main main.cpp)
