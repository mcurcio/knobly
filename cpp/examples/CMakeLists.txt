# The user guide's samples (examples/samples.json; .claude/design/cpp/frozen-docs.md): one program per
# examples/<id>.cpp, built with the tests' warnings, and test examples_<id>, which runs it in a fresh copy of its
# fixture folder and compares what it prints with examples/expected/<id>.txt byte for byte (run_example.cmake). The
# same table drives ts/examples/examples.test.ts and py/tests/test_examples.py, so the three bindings' samples print
# the same text. Included from ../CMakeLists.txt under KNOBLY_BUILD_TESTS.
set(_knobly_samples "${KNOBLY_REPO}/examples")
file(READ "${_knobly_samples}/samples.json" _knobly_table)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${_knobly_samples}/samples.json")
file(GLOB _knobly_examples CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/*.cpp")
foreach(_knobly_example IN LISTS _knobly_examples)
  get_filename_component(_knobly_id "${_knobly_example}" NAME_WE)
  string(JSON _knobly_fixture_type ERROR_VARIABLE _knobly_missing TYPE "${_knobly_table}" samples
         ${_knobly_id} fixture)
  if(_knobly_missing)
    message(FATAL_ERROR "examples/${_knobly_id}.cpp is not in examples/samples.json")
  endif()
  # GET gives an empty string for a JSON null, so ask the type: null runs in an empty folder.
  if(_knobly_fixture_type STREQUAL "NULL")
    set(_knobly_fixture "")
  else()
    string(JSON _knobly_fixture GET "${_knobly_table}" samples ${_knobly_id} fixture)
    set(_knobly_fixture "${KNOBLY_REPO}/${_knobly_fixture}")
  endif()
  add_executable(knobly_example_${_knobly_id} "${_knobly_example}")
  target_link_libraries(knobly_example_${_knobly_id} PRIVATE ${_knobly_program_libraries})
  knobly_test_target(knobly_example_${_knobly_id})
  add_test(NAME examples_${_knobly_id}
           COMMAND ${CMAKE_COMMAND} -DPROGRAM=$<TARGET_FILE:knobly_example_${_knobly_id}>
                   "-DFIXTURE=${_knobly_fixture}" "-DEXPECTED=${_knobly_samples}/expected/${_knobly_id}.txt"
                   "-DWORK=${CMAKE_CURRENT_BINARY_DIR}/runs/${_knobly_id}"
                   -P "${CMAKE_CURRENT_SOURCE_DIR}/run_example.cmake")
endforeach()
