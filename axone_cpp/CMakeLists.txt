# CMakeLists.txt

cmake_minimum_required(VERSION 3.10)
project(MyProject)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED True)

find_library(JSONCPP jsoncpp)

add_executable(main main.cpp)

target_link_libraries(main jsoncpp)