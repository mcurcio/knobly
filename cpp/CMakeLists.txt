# The C++ binding: one header-only INTERFACE target, villanelle::villanelle (design.md 2.5; frozen-m1.md section 5).
#
#   VILLANELLE_REGENERATE   run tools/gen.sh cpp at configure time (Python 3.9+ and uv, for the pinned clang-format);
#                           ON by default when the generated headers are absent, as in a git checkout
#   VILLANELLE_COMPILED     compiled mode: VILLANELLE_HEADER_ONLY=0 for every user of the target; the program compiles
#                           <villanelle/implementation.hpp> in exactly one file
#   VILLANELLE_BUILD_TESTS  the conformance adapter and the binding's own tests (ON when this is the top-level project)
cmake_minimum_required(VERSION 3.24)
project(villanelle LANGUAGES CXX)

get_filename_component(VILLANELLE_REPO "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
set(VILLANELLE_INCLUDE "${CMAKE_CURRENT_SOURCE_DIR}/include")

if(EXISTS "${VILLANELLE_INCLUDE}/villanelle/villanelle.hpp")
  set(_villanelle_regenerate_default OFF)
else()
  set(_villanelle_regenerate_default ON)
endif()
option(VILLANELLE_REGENERATE "Generate the headers from spec/schema/ and grammar/ (tools/gen.sh cpp)"
       ${_villanelle_regenerate_default})
option(VILLANELLE_COMPILED "Compiled mode: define VILLANELLE_HEADER_ONLY=0" OFF)
option(VILLANELLE_BUILD_TESTS "Build the conformance adapter and the binding's tests" ${PROJECT_IS_TOP_LEVEL})

if(VILLANELLE_REGENERATE)
  find_program(VILLANELLE_BASH bash REQUIRED)
  execute_process(COMMAND "${VILLANELLE_BASH}" tools/gen.sh cpp WORKING_DIRECTORY "${VILLANELLE_REPO}"
                  RESULT_VARIABLE _villanelle_gen)
  if(NOT _villanelle_gen EQUAL 0)
    message(FATAL_ERROR "tools/gen.sh cpp failed (${_villanelle_gen})")
  endif()
  # A change to the schema, the grammar or a generator re-runs configure, so the headers never go stale.
  file(GLOB _villanelle_inputs CONFIGURE_DEPENDS "${VILLANELLE_REPO}/spec/schema/*.json"
       "${VILLANELLE_REPO}/grammar/Villanelle.g4" "${VILLANELLE_REPO}/tools/api/*.py"
       "${VILLANELLE_REPO}/tools/parser/*.py" "${VILLANELLE_REPO}/tools/gen-api.py" "${VILLANELLE_REPO}/tools/gen.sh"
       "${CMAKE_CURRENT_SOURCE_DIR}/.clang-format")
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${_villanelle_inputs})
endif()

add_library(villanelle INTERFACE)
add_library(villanelle::villanelle ALIAS villanelle)
target_include_directories(villanelle INTERFACE $<BUILD_INTERFACE:${VILLANELLE_INCLUDE}> $<INSTALL_INTERFACE:include>)
target_compile_features(villanelle INTERFACE cxx_std_20)
if(VILLANELLE_COMPILED)
  target_compile_definitions(villanelle INTERFACE VILLANELLE_HEADER_ONLY=0)
endif()

if(VILLANELLE_BUILD_TESTS)
  enable_testing()
  # Compiled, never linked: the headers together, the generated parser against its hooks, and the generated contract
  # and layer check (SKELETON: Slice T links the contract of each implemented layer and adds Catch2 and the driver).
  file(GLOB _villanelle_generated_tests "${CMAKE_CURRENT_SOURCE_DIR}/tests/generated/*.cpp")
  set(_villanelle_compile_checks tests/compile/headers.cpp tests/compile/support.cpp tests/compile/parser_hooks.cpp
                                 ${_villanelle_generated_tests})
  if(VILLANELLE_COMPILED)
    list(APPEND _villanelle_compile_checks tests/compile/implementation.cpp)
  endif()
  add_library(villanelle_compile_check OBJECT ${_villanelle_compile_checks})
  target_link_libraries(villanelle_compile_check PRIVATE villanelle::villanelle)
  target_compile_options(villanelle_compile_check PRIVATE
                         $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-Wall -Wextra -Werror> $<$<CXX_COMPILER_ID:MSVC>:/W4 /WX>)

  add_executable(villanelle_adapter conformance/adapter.cpp)
  target_link_libraries(villanelle_adapter PRIVATE villanelle::villanelle)
endif()
