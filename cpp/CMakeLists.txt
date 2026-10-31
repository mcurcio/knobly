# The C++ binding: one header-only INTERFACE target, knobly::knobly (design.md 2.5; frozen-m1.md section 5).
# Nothing is installed: a program takes it with FetchContent or add_subdirectory of the release source archive (or a
# vendored copy), or copies the single header (README.md, "Using it"; frozen-docs.md section 6).
#
#   KNOBLY_REGENERATE   run tools/gen.sh cpp at configure time (Python 3.9+ and uv, for the pinned clang-format);
#                           ON by default when the generated headers are absent, as in a git checkout (the release
#                           source archive carries them, so it builds with no Python and no network)
#   KNOBLY_COMPILED     compiled mode: KNOBLY_HEADER_ONLY=0 for every user of the target in this build; the
#                           program compiles <knobly/implementation.hpp> in exactly one file (README.md)
#   KNOBLY_BUILD_TESTS  the conformance adapter and the binding's own tests (ON when this is the top-level project
#                           and tests/ is present: the release source archive leaves it out)
#   KNOBLY_SANITIZE     build the tests with AddressSanitizer and UndefinedBehaviorSanitizer (GCC, Clang)
cmake_minimum_required(VERSION 3.24)

# The version's one home is include/knobly/support/config.hpp (0.0.0 in the repository, stamped at release).
file(STRINGS "${CMAKE_CURRENT_LIST_DIR}/include/knobly/support/config.hpp" _knobly_version_lines
     REGEX "^#define KNOBLY_VERSION_(MAJOR|MINOR|PATCH) [0-9]+$")
set(_knobly_version "")
foreach(_knobly_part IN ITEMS MAJOR MINOR PATCH)
  string(REGEX MATCH "KNOBLY_VERSION_${_knobly_part} ([0-9]+)" _knobly_match "${_knobly_version_lines}")
  if(NOT _knobly_match)
    message(FATAL_ERROR "include/knobly/support/config.hpp: no KNOBLY_VERSION_${_knobly_part}")
  endif()
  list(APPEND _knobly_version "${CMAKE_MATCH_1}")
endforeach()
list(JOIN _knobly_version "." _knobly_version)
project(knobly VERSION ${_knobly_version} LANGUAGES CXX)

get_filename_component(KNOBLY_REPO "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
set(KNOBLY_INCLUDE "${CMAKE_CURRENT_SOURCE_DIR}/include")

if(EXISTS "${KNOBLY_INCLUDE}/knobly/knobly.hpp")
  set(_knobly_regenerate_default OFF)
else()
  set(_knobly_regenerate_default ON)
endif()
if(PROJECT_IS_TOP_LEVEL AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/tests")
  set(_knobly_tests_default ON)
else()
  set(_knobly_tests_default OFF)
endif()
option(KNOBLY_REGENERATE "Generate the headers from spec/schema/ and grammar/ (tools/gen.sh cpp)"
       ${_knobly_regenerate_default})
option(KNOBLY_COMPILED "Compiled mode: define KNOBLY_HEADER_ONLY=0" OFF)
option(KNOBLY_BUILD_TESTS "Build the conformance adapter and the binding's tests" ${_knobly_tests_default})
option(KNOBLY_SANITIZE "Build the tests with -fsanitize=address,undefined" OFF)

if(KNOBLY_REGENERATE)
  find_program(KNOBLY_BASH bash REQUIRED)
  execute_process(COMMAND "${KNOBLY_BASH}" tools/gen.sh cpp WORKING_DIRECTORY "${KNOBLY_REPO}"
                  RESULT_VARIABLE _knobly_gen)
  if(NOT _knobly_gen EQUAL 0)
    message(FATAL_ERROR "tools/gen.sh cpp failed (${_knobly_gen})")
  endif()
  # A change to the schema, the grammar or a generator re-runs configure, so the headers never go stale.
  file(GLOB _knobly_inputs CONFIGURE_DEPENDS "${KNOBLY_REPO}/spec/schema/*.json"
       "${KNOBLY_REPO}/grammar/Knobly.g4" "${KNOBLY_REPO}/tools/api/*.py"
       "${KNOBLY_REPO}/tools/parser/*.py" "${KNOBLY_REPO}/tools/gen-api.py" "${KNOBLY_REPO}/tools/gen.sh"
       "${CMAKE_CURRENT_SOURCE_DIR}/.clang-format")
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${_knobly_inputs})
endif()

add_library(knobly INTERFACE)
add_library(knobly::knobly ALIAS knobly)
target_include_directories(knobly INTERFACE "${KNOBLY_INCLUDE}")
target_compile_features(knobly INTERFACE cxx_std_20)
if(KNOBLY_COMPILED)
  target_compile_definitions(knobly INTERFACE KNOBLY_HEADER_ONLY=0)
endif()

if(KNOBLY_BUILD_TESTS)
  enable_testing()
  find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)

  # Catch2 v3, for the tests only (design.md 2.6), pinned by tag and archive hash.
  include(FetchContent)
  FetchContent_Declare(Catch2 URL https://github.com/catchorg/Catch2/archive/refs/tags/v3.7.1.tar.gz
                       URL_HASH SHA256=c991b247a1a0d7bb9c39aa35faf0fe9e19764213f28ffba3109388e62ee0269c)
  FetchContent_MakeAvailable(Catch2)

  # Every test target: warnings as errors, and the sanitizers when asked.
  function(knobly_test_target target)
    target_compile_options(${target} PRIVATE $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-Wall -Wextra -Werror>
                                             $<$<CXX_COMPILER_ID:MSVC>:/W4 /WX>)
    if(KNOBLY_SANITIZE)
      target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-sanitize-recover=all
                                               -fno-omit-frame-pointer)
      target_link_options(${target} PRIVATE -fsanitize=address,undefined)
    endif()
  endfunction()

  # Compiled mode: the one implementation file, linked into every test program.
  if(KNOBLY_COMPILED)
    add_library(knobly_implementation STATIC tests/compile/implementation.cpp)
    target_link_libraries(knobly_implementation PUBLIC knobly::knobly)
    knobly_test_target(knobly_implementation)
    set(_knobly_program_libraries knobly_implementation)
  else()
    set(_knobly_program_libraries knobly::knobly)
  endif()

  # Compiled, never linked: the headers together, the generated parser against its hooks, and the generated layer
  # check (a header that includes a layer it may not import fails to compile).
  file(GLOB _knobly_layer_checks "${CMAKE_CURRENT_SOURCE_DIR}/tests/generated/layers_*.cpp")
  add_library(knobly_compile_check OBJECT tests/compile/headers.cpp tests/compile/support.cpp
                                              tests/compile/parser_hooks.cpp tests/compile/unions.cpp
                                              ${_knobly_layer_checks})
  target_link_libraries(knobly_compile_check PRIVATE knobly::knobly)
  knobly_test_target(knobly_compile_check)

  # The syntax layer with exceptions and RTTI off: nothing in it throws or asks a type at run time.
  add_library(knobly_no_exceptions OBJECT tests/compile/no_exceptions.cpp)
  target_link_libraries(knobly_no_exceptions PRIVATE knobly::knobly)
  target_compile_options(knobly_no_exceptions PRIVATE $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-fno-exceptions
                                                          -fno-rtti> $<$<CXX_COMPILER_ID:MSVC>:/EHs-c- /GR->)
  knobly_test_target(knobly_no_exceptions)

  # The generated contract of every public header: a declaration without a definition fails to link.
  file(GLOB _knobly_contracts CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/tests/generated/api_contract_*.cpp")
  foreach(_knobly_contract IN LISTS _knobly_contracts)
    get_filename_component(_knobly_stem "${_knobly_contract}" NAME_WE)
    string(REPLACE "api_contract_" "" _knobly_stem "${_knobly_stem}")
    add_executable(knobly_contract_${_knobly_stem} "${_knobly_contract}")
    target_link_libraries(knobly_contract_${_knobly_stem} PRIVATE ${_knobly_program_libraries})
    knobly_test_target(knobly_contract_${_knobly_stem})
    add_test(NAME contract_${_knobly_stem} COMMAND knobly_contract_${_knobly_stem})
  endforeach()

  # One Catch2 program per file of tests/unit/: knobly_unit_<name>, test unit_<name>, so each slice builds and runs
  # its own (cmake --build ... --target knobly_unit_<name>; ctest -R unit_<name>) beside another's work in progress.
  file(GLOB _knobly_unit_tests CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/tests/unit/*.cpp")
  foreach(_knobly_unit IN LISTS _knobly_unit_tests)
    get_filename_component(_knobly_stem "${_knobly_unit}" NAME_WE)
    add_executable(knobly_unit_${_knobly_stem} "${_knobly_unit}")
    target_link_libraries(knobly_unit_${_knobly_stem} PRIVATE ${_knobly_program_libraries}
                                                                       Catch2::Catch2WithMain)
    knobly_test_target(knobly_unit_${_knobly_stem})
    add_test(NAME unit_${_knobly_stem} COMMAND knobly_unit_${_knobly_stem}
             WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}")
  endforeach()

  # The design's programs as a user writes them (design.md 4; frozen-m2.md 6, frozen-m3.md 4): sinks (4.1), editor
  # (4.2) and lint (4.3), each with the stricter warnings the design names. Test programs_<name> runs it once per run
  # folder of tests/programs/<name>_expected/, in a fresh copy of tests/programs/<name>/, and compares its output, its
  # exit status and (for the editor) the files it saved (tests/programs/run_program.cmake).
  function(knobly_program name)
    add_executable(knobly_program_${name} tests/programs/${name}.cpp)
    target_link_libraries(knobly_program_${name} PRIVATE ${_knobly_program_libraries})
    knobly_test_target(knobly_program_${name})
    target_compile_options(knobly_program_${name}
                           PRIVATE $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-Wsign-conversion>
                                   $<$<CXX_COMPILER_ID:Clang,AppleClang>:-Wdangling>)
    set(_programs "${CMAKE_CURRENT_SOURCE_DIR}/tests/programs")
    add_test(NAME programs_${name}
             COMMAND ${CMAKE_COMMAND} -DPROGRAM=$<TARGET_FILE:knobly_program_${name}> "-DFIXTURE=${_programs}/${name}"
                     "-DEXPECTED=${_programs}/${name}_expected" "-DWORK=${CMAKE_CURRENT_BINARY_DIR}/programs/${name}"
                     -P "${_programs}/run_program.cmake")
  endfunction()
  foreach(_knobly_program_name IN ITEMS sinks editor lint)
    knobly_program(${_knobly_program_name})
  endforeach()

  # What C++ refuses at compile time that the dynamically typed bindings refuse at run time (design.md 2.6, finding
  # F1; frozen-m3.md 4): each tests/compile_fail/<name>.cpp holds the refused line, and under KNOBLY_CONTROL the
  # nearest valid one. Both are object libraries left out of the default build; test compile_fail_<name> builds the
  # first and must fail, compile_fail_<name>_control builds the second and must succeed, so the failure is the
  # refused line and not a typo.
  file(GLOB _knobly_compile_fails CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/tests/compile_fail/*.cpp")
  foreach(_knobly_compile_fail IN LISTS _knobly_compile_fails)
    get_filename_component(_knobly_stem "${_knobly_compile_fail}" NAME_WE)
    foreach(_knobly_variant IN ITEMS refused control)
      set(_knobly_target knobly_compile_fail_${_knobly_stem}_${_knobly_variant})
      add_library(${_knobly_target} OBJECT EXCLUDE_FROM_ALL "${_knobly_compile_fail}")
      target_link_libraries(${_knobly_target} PRIVATE knobly::knobly)
      knobly_test_target(${_knobly_target})
      set(_knobly_test compile_fail_${_knobly_stem})
      if(_knobly_variant STREQUAL "control")
        target_compile_definitions(${_knobly_target} PRIVATE KNOBLY_CONTROL)
        string(APPEND _knobly_test "_control")
      endif()
      add_test(NAME ${_knobly_test} COMMAND ${CMAKE_COMMAND} --build "${CMAKE_BINARY_DIR}" --target
                                                ${_knobly_target} --config $<CONFIG>)
      if(_knobly_variant STREQUAL "refused")
        set_tests_properties(${_knobly_test} PROPERTIES WILL_FAIL TRUE)
      endif()
    endforeach()
  endforeach()

  # The user guide's samples, each run against its expected output (examples/CMakeLists.txt). The release source
  # archive leaves examples/ out with tests/.
  if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/examples/CMakeLists.txt")
    add_subdirectory(examples)
  endif()

  add_executable(knobly_adapter conformance/adapter.cpp)
  target_link_libraries(knobly_adapter PRIVATE ${_knobly_program_libraries})
  knobly_test_target(knobly_adapter)
  # The shared driver (spec/conformance.md) runs every case up to the level the adapter claims (its hello). A stalled
  # adapter fails the test instead of hanging the run (kno-p5x; the driver also times out each request).
  add_test(NAME conformance COMMAND Python3::Interpreter "${KNOBLY_REPO}/conformance/driver/run.py"
                                    -- $<TARGET_FILE:knobly_adapter>)
  set_tests_properties(conformance PROPERTIES TIMEOUT 900)
  # The adapter's JSON is freed and written without recursing (kno-bzv.10): the deepest load case runs again with the
  # adapter's stack lowered to 512 KiB (four times that under the sanitizers), where a destructor or dump that recursed
  # once per level overflows. It passes on 384 KiB. POSIX shells only (`ulimit -s`).
  if(UNIX)
    if(KNOBLY_SANITIZE)
      set(_knobly_adapter_stack_kib 2048)
    else()
      set(_knobly_adapter_stack_kib 512)
    endif()
    add_test(NAME conformance_small_stack
             COMMAND sh -c "ulimit -s ${_knobly_adapter_stack_kib} && exec \"$0\" \"$1\" --case load-expanded-nesting-256 -- \"$2\""
                     "${Python3_EXECUTABLE}" "${KNOBLY_REPO}/conformance/driver/run.py" $<TARGET_FILE:knobly_adapter>)
    set_tests_properties(conformance_small_stack PROPERTIES TIMEOUT 120)
  endif()
endif()
