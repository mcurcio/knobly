# A consumer of an installed villanelle (CI's C++ package job): configure with -DCMAKE_PREFIX_PATH=<install prefix>,
# build, and run the program (consumer.cpp; it exits 0 only on the expected output). VILLANELLE_WANTED is the version
# asked of find_package (the package's version file accepts the same major version); VILLANELLE_COMPILED builds the
# program in compiled mode, with the one implementation file.
cmake_minimum_required(VERSION 3.24)
project(villanelle_consumer LANGUAGES CXX)

set(VILLANELLE_WANTED "" CACHE STRING "The version asked of find_package(villanelle)")
option(VILLANELLE_COMPILED "Compiled mode: define VILLANELLE_HEADER_ONLY=0 and compile implementation.hpp once" OFF)

find_package(villanelle ${VILLANELLE_WANTED} REQUIRED CONFIG)

add_executable(consumer consumer.cpp)
target_link_libraries(consumer PRIVATE villanelle::villanelle)
if(VILLANELLE_COMPILED)
  target_sources(consumer PRIVATE implementation.cpp)
  target_compile_definitions(consumer PRIVATE VILLANELLE_HEADER_ONLY=0)
endif()
