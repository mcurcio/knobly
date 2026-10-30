# The programs_editor test (frozen-m2.md 6): run design program 4.2 in a fresh copy of tests/programs/editor/, then
# compare both files with tests/programs/editor_expected/ ($pixels 2400, fps 30;, comments kept).
#   cmake -DPROGRAM=<editor> -DSOURCE=<tests/programs> -DWORK=<scratch directory> -P run_editor.cmake
file(REMOVE_RECURSE "${WORK}")
file(COPY "${SOURCE}/editor/" DESTINATION "${WORK}")
execute_process(COMMAND "${PROGRAM}" WORKING_DIRECTORY "${WORK}" RESULT_VARIABLE status OUTPUT_VARIABLE out
                ERROR_VARIABLE err)
message(STATUS "editor said:\n${out}${err}")
if(NOT status EQUAL 0)
  message(FATAL_ERROR "the editor exited with ${status}")
endif()
foreach(name IN ITEMS main.conf sink.conf)
  file(READ "${WORK}/${name}" actual)
  file(READ "${SOURCE}/editor_expected/${name}" expected)
  if(NOT actual STREQUAL expected)
    message(FATAL_ERROR "${name} after the editor:\n${actual}\nexpected:\n${expected}")
  endif()
endforeach()
