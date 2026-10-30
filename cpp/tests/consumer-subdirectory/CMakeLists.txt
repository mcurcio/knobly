# A program taking villanelle with add_subdirectory of the extracted release source archive (or a vendored copy):
# VILLANELLE_SOURCE is that folder. cpp/tests/consumer/check.sh builds and runs it; nothing is installed.
cmake_minimum_required(VERSION 3.24)
project(villanelle_consumer_subdirectory LANGUAGES CXX)

set(VILLANELLE_SOURCE "" CACHE PATH "The extracted release archive: villanelle-cpp-<version>/")

add_subdirectory("${VILLANELLE_SOURCE}" villanelle)

add_executable(consumer ../consumer/consumer.cpp)
target_link_libraries(consumer PRIVATE villanelle::villanelle)
