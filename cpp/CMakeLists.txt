# The C++ binding: one header-only INTERFACE target, villanelle::villanelle (design.md 2.5; frozen-m1.md section 5).
#
#   VILLANELLE_REGENERATE   run tools/gen.sh cpp at configure time (Python 3.9+ and uv, for the pinned clang-format);
#                           ON by default when the generated headers are absent, as in a git checkout
#   VILLANELLE_COMPILED     compiled mode: VILLANELLE_HEADER_ONLY=0 for every user of the target; the program compiles
#                           <villanelle/implementation.hpp> in exactly one file
#   VILLANELLE_BUILD_TESTS  the conformance adapter and the binding's own tests (ON when this is the top-level project)
#   VILLANELLE_SANITIZE     build the tests with AddressSanitizer and UndefinedBehaviorSanitizer (GCC, Clang)
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
option(VILLANELLE_SANITIZE "Build the tests with -fsanitize=address,undefined" OFF)

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
  find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)

  # Catch2 v3, for the tests only (design.md 2.6), pinned by tag and archive hash.
  include(FetchContent)
  FetchContent_Declare(Catch2 URL https://github.com/catchorg/Catch2/archive/refs/tags/v3.7.1.tar.gz
                       URL_HASH SHA256=c991b247a1a0d7bb9c39aa35faf0fe9e19764213f28ffba3109388e62ee0269c)
  FetchContent_MakeAvailable(Catch2)

  # Every test target: warnings as errors, and the sanitizers when asked.
  function(villanelle_test_target target)
    target_compile_options(${target} PRIVATE $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-Wall -Wextra -Werror>
                                             $<$<CXX_COMPILER_ID:MSVC>:/W4 /WX>)
    if(VILLANELLE_SANITIZE)
      target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-sanitize-recover=all
                                               -fno-omit-frame-pointer)
      target_link_options(${target} PRIVATE -fsanitize=address,undefined)
    endif()
  endfunction()

  # Compiled mode: the one implementation file, linked into every test program.
  if(VILLANELLE_COMPILED)
    add_library(villanelle_implementation STATIC tests/compile/implementation.cpp)
    target_link_libraries(villanelle_implementation PUBLIC villanelle::villanelle)
    villanelle_test_target(villanelle_implementation)
    set(_villanelle_program_libraries villanelle_implementation)
  else()
    set(_villanelle_program_libraries villanelle::villanelle)
  endif()

  # Compiled, never linked: the headers together, the generated parser against its hooks, and the generated layer
  # check (a header that includes a layer it may not import fails to compile).
  file(GLOB _villanelle_layer_checks "${CMAKE_CURRENT_SOURCE_DIR}/tests/generated/layers_*.cpp")
  add_library(villanelle_compile_check OBJECT tests/compile/headers.cpp tests/compile/support.cpp
                                              tests/compile/parser_hooks.cpp tests/compile/unions.cpp
                                              ${_villanelle_layer_checks})
  target_link_libraries(villanelle_compile_check PRIVATE villanelle::villanelle)
  villanelle_test_target(villanelle_compile_check)

  # The syntax layer with exceptions and RTTI off: nothing in it throws or asks a type at run time.
  add_library(villanelle_no_exceptions OBJECT tests/compile/no_exceptions.cpp)
  target_link_libraries(villanelle_no_exceptions PRIVATE villanelle::villanelle)
  target_compile_options(villanelle_no_exceptions PRIVATE $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-fno-exceptions
                                                          -fno-rtti> $<$<CXX_COMPILER_ID:MSVC>:/EHs-c- /GR->)
  villanelle_test_target(villanelle_no_exceptions)

  # The generated contract of every public header: a declaration without a definition fails to link (milestone 2
  # defines every declaration, as a stub until its slice lands: frozen-m2.md section 2).
  file(GLOB _villanelle_contracts CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/tests/generated/api_contract_*.cpp")
  foreach(_villanelle_contract IN LISTS _villanelle_contracts)
    get_filename_component(_villanelle_stem "${_villanelle_contract}" NAME_WE)
    string(REPLACE "api_contract_" "" _villanelle_stem "${_villanelle_stem}")
    add_executable(villanelle_contract_${_villanelle_stem} "${_villanelle_contract}")
    target_link_libraries(villanelle_contract_${_villanelle_stem} PRIVATE ${_villanelle_program_libraries})
    villanelle_test_target(villanelle_contract_${_villanelle_stem})
    add_test(NAME contract_${_villanelle_stem} COMMAND villanelle_contract_${_villanelle_stem})
  endforeach()

  # One Catch2 program per file of tests/unit/: villanelle_unit_<name>, test unit_<name>, so each slice builds and runs
  # its own (cmake --build ... --target villanelle_unit_<name>; ctest -R unit_<name>) beside another's work in progress.
  file(GLOB _villanelle_unit_tests CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/tests/unit/*.cpp")
  foreach(_villanelle_unit IN LISTS _villanelle_unit_tests)
    get_filename_component(_villanelle_stem "${_villanelle_unit}" NAME_WE)
    add_executable(villanelle_unit_${_villanelle_stem} "${_villanelle_unit}")
    target_link_libraries(villanelle_unit_${_villanelle_stem} PRIVATE ${_villanelle_program_libraries}
                                                                       Catch2::Catch2WithMain)
    villanelle_test_target(villanelle_unit_${_villanelle_stem})
    add_test(NAME unit_${_villanelle_stem} COMMAND villanelle_unit_${_villanelle_stem}
             WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}")
  endforeach()

  add_executable(villanelle_adapter conformance/adapter.cpp)
  target_link_libraries(villanelle_adapter PRIVATE ${_villanelle_program_libraries})
  villanelle_test_target(villanelle_adapter)
  # The shared driver (spec/conformance.md) runs every case up to the level the adapter claims (its hello). A stalled
  # adapter fails the test instead of hanging the run (vil-p5x; the driver also times out each request).
  add_test(NAME conformance COMMAND Python3::Interpreter "${VILLANELLE_REPO}/conformance/driver/run.py"
                                    -- $<TARGET_FILE:villanelle_adapter>)
  set_tests_properties(conformance PROPERTIES TIMEOUT 900)
endif()
