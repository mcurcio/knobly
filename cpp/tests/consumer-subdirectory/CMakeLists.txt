# A program taking knobly with add_subdirectory of the extracted release source archive (or a vendored copy):
# KNOBLY_SOURCE is that folder. cpp/tests/consumer/check.sh builds and runs it; nothing is installed.
cmake_minimum_required(VERSION 3.24)
project(knobly_consumer_subdirectory LANGUAGES CXX)

set(KNOBLY_SOURCE "" CACHE PATH "The extracted release archive: knobly-cpp-<version>/")

add_subdirectory("${KNOBLY_SOURCE}" knobly)

add_executable(consumer ../consumer/consumer.cpp)
target_link_libraries(consumer PRIVATE knobly::knobly)
