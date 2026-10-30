# The user guide's samples (examples/samples.json; .claude/design/cpp/frozen-docs.md): one program per
# examples/<id>.cpp, built with the tests' warnings, and test examples_<id>, which runs it in a fresh copy of its
# fixture folder and compares what it prints with examples/expected/<id>.txt byte for byte (run_example.cmake). The
# same table drives ts/examples/examples.test.ts and py/tests/test_examples.py, so the three bindings' samples print
# the same text. Included from ../CMakeLists.txt under VILLANELLE_BUILD_TESTS.
set(_villanelle_samples "${VILLANELLE_REPO}/examples")
file(READ "${_villanelle_samples}/samples.json" _villanelle_table)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${_villanelle_samples}/samples.json")
file(GLOB _villanelle_examples CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/*.cpp")
foreach(_villanelle_example IN LISTS _villanelle_examples)
  get_filename_component(_villanelle_id "${_villanelle_example}" NAME_WE)
  string(JSON _villanelle_fixture ERROR_VARIABLE _villanelle_missing GET "${_villanelle_table}" samples
         ${_villanelle_id} fixture)
  if(_villanelle_missing)
    message(FATAL_ERROR "examples/${_villanelle_id}.cpp is not in examples/samples.json")
  endif()
  if(_villanelle_fixture STREQUAL "null")
    set(_villanelle_fixture "")
  else()
    set(_villanelle_fixture "${VILLANELLE_REPO}/${_villanelle_fixture}")
  endif()
  add_executable(villanelle_example_${_villanelle_id} "${_villanelle_example}")
  target_link_libraries(villanelle_example_${_villanelle_id} PRIVATE ${_villanelle_program_libraries})
  villanelle_test_target(villanelle_example_${_villanelle_id})
  add_test(NAME examples_${_villanelle_id}
           COMMAND ${CMAKE_COMMAND} -DPROGRAM=$<TARGET_FILE:villanelle_example_${_villanelle_id}>
                   "-DFIXTURE=${_villanelle_fixture}" "-DEXPECTED=${_villanelle_samples}/expected/${_villanelle_id}.txt"
                   "-DWORK=${CMAKE_CURRENT_BINARY_DIR}/runs/${_villanelle_id}"
                   -P "${CMAKE_CURRENT_SOURCE_DIR}/run_example.cmake")
endforeach()
