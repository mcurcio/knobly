# The C++ binding: one header-only INTERFACE target, villanelle::villanelle (design.md 2.5; frozen-m1.md section 5).
#
#   VILLANELLE_REGENERATE   run tools/gen.sh cpp at configure time (Python 3.9+ and uv, for the pinned clang-format);
#                           ON by default when the generated headers are absent, as in a git checkout (the release
#                           source archive carries them, so it builds with no Python and no network)
#   VILLANELLE_COMPILED     compiled mode: VILLANELLE_HEADER_ONLY=0 for every user of the target in this build; the
#                           program compiles <villanelle/implementation.hpp> in exactly one file. Never installed: a
#                           program using an installed villanelle defines VILLANELLE_HEADER_ONLY=0 itself (README.md)
#   VILLANELLE_INSTALL      cmake --install puts the headers and the package config, with its version file, in place,
#                           so find_package(villanelle) works (ON when this is the top-level project)
#   VILLANELLE_BUILD_TESTS  the conformance adapter and the binding's own tests (ON when this is the top-level project
#                           and tests/ is present: the release source archive leaves it out)
#   VILLANELLE_SANITIZE     build the tests with AddressSanitizer and UndefinedBehaviorSanitizer (GCC, Clang)
cmake_minimum_required(VERSION 3.24)

# The version's one home is include/villanelle/support/config.hpp (0.0.0 in the repository, stamped at release).
file(STRINGS "${CMAKE_CURRENT_LIST_DIR}/include/villanelle/support/config.hpp" _villanelle_version_lines
     REGEX "^#define VILLANELLE_VERSION_(MAJOR|MINOR|PATCH) [0-9]+$")
set(_villanelle_version "")
foreach(_villanelle_part IN ITEMS MAJOR MINOR PATCH)
  string(REGEX MATCH "VILLANELLE_VERSION_${_villanelle_part} ([0-9]+)" _villanelle_match "${_villanelle_version_lines}")
  if(NOT _villanelle_match)
    message(FATAL_ERROR "include/villanelle/support/config.hpp: no VILLANELLE_VERSION_${_villanelle_part}")
  endif()
  list(APPEND _villanelle_version "${CMAKE_MATCH_1}")
endforeach()
list(JOIN _villanelle_version "." _villanelle_version)
project(villanelle VERSION ${_villanelle_version} LANGUAGES CXX)

include(GNUInstallDirs)
get_filename_component(VILLANELLE_REPO "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
set(VILLANELLE_INCLUDE "${CMAKE_CURRENT_SOURCE_DIR}/include")

if(EXISTS "${VILLANELLE_INCLUDE}/villanelle/villanelle.hpp")
  set(_villanelle_regenerate_default OFF)
else()
  set(_villanelle_regenerate_default ON)
endif()
if(PROJECT_IS_TOP_LEVEL AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/tests")
  set(_villanelle_tests_default ON)
else()
  set(_villanelle_tests_default OFF)
endif()
option(VILLANELLE_REGENERATE "Generate the headers from spec/schema/ and grammar/ (tools/gen.sh cpp)"
       ${_villanelle_regenerate_default})
option(VILLANELLE_COMPILED "Compiled mode: define VILLANELLE_HEADER_ONLY=0" OFF)
option(VILLANELLE_INSTALL "Install the headers and the package config" ${PROJECT_IS_TOP_LEVEL})
option(VILLANELLE_BUILD_TESTS "Build the conformance adapter and the binding's tests" ${_villanelle_tests_default})
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
target_include_directories(villanelle INTERFACE $<BUILD_INTERFACE:${VILLANELLE_INCLUDE}>
                                                $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)
target_compile_features(villanelle INTERFACE cxx_std_20)
if(VILLANELLE_COMPILED)
  target_compile_definitions(villanelle INTERFACE $<BUILD_INTERFACE:VILLANELLE_HEADER_ONLY=0>)
endif()

# The install: the headers (the generated ones included, made at configure time) and the exported target as the
# package config, with a version file accepting the same major version. Header-only, so the package is
# architecture-independent and goes under the data directory (share/cmake/villanelle).
if(VILLANELLE_INSTALL)
  include(CMakePackageConfigHelpers)
  set(_villanelle_package "${CMAKE_INSTALL_DATADIR}/cmake/villanelle")
  install(TARGETS villanelle EXPORT villanelle)
  install(DIRECTORY "${VILLANELLE_INCLUDE}/villanelle" DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
          FILES_MATCHING PATTERN "*.hpp" PATTERN ".*" EXCLUDE)
  install(EXPORT villanelle NAMESPACE villanelle:: FILE villanelle-config.cmake DESTINATION "${_villanelle_package}")
  write_basic_package_version_file("${CMAKE_CURRENT_BINARY_DIR}/villanelle-config-version.cmake"
                                   COMPATIBILITY SameMajorVersion ARCH_INDEPENDENT)
  install(FILES "${CMAKE_CURRENT_BINARY_DIR}/villanelle-config-version.cmake" DESTINATION "${_villanelle_package}")
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

  # The generated contract of every public header: a declaration without a definition fails to link.
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

  # The design's programs as a user writes them (design.md 4; frozen-m2.md 6, frozen-m3.md 4): sinks (4.1), editor
  # (4.2) and lint (4.3), each with the stricter warnings the design names. Test programs_<name> runs it once per run
  # folder of tests/programs/<name>_expected/, in a fresh copy of tests/programs/<name>/, and compares its output, its
  # exit status and (for the editor) the files it saved (tests/programs/run_program.cmake).
  function(villanelle_program name)
    add_executable(villanelle_program_${name} tests/programs/${name}.cpp)
    target_link_libraries(villanelle_program_${name} PRIVATE ${_villanelle_program_libraries})
    villanelle_test_target(villanelle_program_${name})
    target_compile_options(villanelle_program_${name}
                           PRIVATE $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-Wsign-conversion>
                                   $<$<CXX_COMPILER_ID:Clang,AppleClang>:-Wdangling>)
    set(_programs "${CMAKE_CURRENT_SOURCE_DIR}/tests/programs")
    add_test(NAME programs_${name}
             COMMAND ${CMAKE_COMMAND} -DPROGRAM=$<TARGET_FILE:villanelle_program_${name}> "-DFIXTURE=${_programs}/${name}"
                     "-DEXPECTED=${_programs}/${name}_expected" "-DWORK=${CMAKE_CURRENT_BINARY_DIR}/programs/${name}"
                     -P "${_programs}/run_program.cmake")
  endfunction()
  foreach(_villanelle_program_name IN ITEMS sinks editor lint)
    villanelle_program(${_villanelle_program_name})
  endforeach()

  # What C++ refuses at compile time that the dynamically typed bindings refuse at run time (design.md 2.6, finding
  # F1; frozen-m3.md 4): each tests/compile_fail/<name>.cpp holds the refused line, and under VILLANELLE_CONTROL the
  # nearest valid one. Both are object libraries left out of the default build; test compile_fail_<name> builds the
  # first and must fail, compile_fail_<name>_control builds the second and must succeed, so the failure is the
  # refused line and not a typo.
  file(GLOB _villanelle_compile_fails CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/tests/compile_fail/*.cpp")
  foreach(_villanelle_compile_fail IN LISTS _villanelle_compile_fails)
    get_filename_component(_villanelle_stem "${_villanelle_compile_fail}" NAME_WE)
    foreach(_villanelle_variant IN ITEMS refused control)
      set(_villanelle_target villanelle_compile_fail_${_villanelle_stem}_${_villanelle_variant})
      add_library(${_villanelle_target} OBJECT EXCLUDE_FROM_ALL "${_villanelle_compile_fail}")
      target_link_libraries(${_villanelle_target} PRIVATE villanelle::villanelle)
      villanelle_test_target(${_villanelle_target})
      set(_villanelle_test compile_fail_${_villanelle_stem})
      if(_villanelle_variant STREQUAL "control")
        target_compile_definitions(${_villanelle_target} PRIVATE VILLANELLE_CONTROL)
        string(APPEND _villanelle_test "_control")
      endif()
      add_test(NAME ${_villanelle_test} COMMAND ${CMAKE_COMMAND} --build "${CMAKE_BINARY_DIR}" --target
                                                ${_villanelle_target} --config $<CONFIG>)
      if(_villanelle_variant STREQUAL "refused")
        set_tests_properties(${_villanelle_test} PROPERTIES WILL_FAIL TRUE)
      endif()
    endforeach()
  endforeach()

  # The user guide's samples, each run against its expected output (examples/CMakeLists.txt). The release source
  # archive leaves examples/ out with tests/.
  if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/examples/CMakeLists.txt")
    add_subdirectory(examples)
  endif()

  add_executable(villanelle_adapter conformance/adapter.cpp)
  target_link_libraries(villanelle_adapter PRIVATE ${_villanelle_program_libraries})
  villanelle_test_target(villanelle_adapter)
  # The shared driver (spec/conformance.md) runs every case up to the level the adapter claims (its hello). A stalled
  # adapter fails the test instead of hanging the run (vil-p5x; the driver also times out each request).
  add_test(NAME conformance COMMAND Python3::Interpreter "${VILLANELLE_REPO}/conformance/driver/run.py"
                                    -- $<TARGET_FILE:villanelle_adapter>)
  set_tests_properties(conformance PROPERTIES TIMEOUT 900)
endif()
