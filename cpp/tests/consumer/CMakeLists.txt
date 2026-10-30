# A program taking knobly with FetchContent of the release source archive, as the user guide's Quickstart shows
# (region fetchcontent; cpp/tests/consumer/check.sh builds and runs it). The archive is downloaded and unpacked into
# this build folder; nothing is installed and no Python is needed. -DKNOBLY_COMPILED=ON is the subproject's own
# option (compiled mode); the program then compiles the one implementation file.
cmake_minimum_required(VERSION 3.24)
project(knobly_consumer LANGUAGES CXX)

set(KNOBLY_RELEASE_URL "" CACHE STRING "The release's URL: knobly-cpp-<version>.tar.gz")
set(KNOBLY_RELEASE_SHA256 "" CACHE STRING "The release archive's SHA-256")

# --8<-- [start:fetchcontent]
include(FetchContent)
FetchContent_Declare(knobly URL ${KNOBLY_RELEASE_URL} URL_HASH SHA256=${KNOBLY_RELEASE_SHA256})
FetchContent_MakeAvailable(knobly)

add_executable(consumer consumer.cpp)
target_link_libraries(consumer PRIVATE knobly::knobly)
# --8<-- [end:fetchcontent]

if(KNOBLY_COMPILED)
  target_sources(consumer PRIVATE implementation.cpp)
endif()
