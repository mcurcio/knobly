# Every examples_<id> test (examples/CMakeLists.txt): run one sample in a fresh copy of its fixture folder and compare
# what it prints with its expected file, byte for byte. The run folder is cut from the output before comparing, as the
# TypeScript runner does (C++'s file source keeps paths relative, so it is a no-op here).
#   cmake -DPROGRAM=<sample> -DFIXTURE=<folder, or empty> -DEXPECTED=<examples/expected/id.txt> -DWORK=<scratch>
#         -P run_example.cmake
file(REMOVE_RECURSE "${WORK}")
file(MAKE_DIRECTORY "${WORK}")
if(NOT FIXTURE STREQUAL "")
  file(COPY "${FIXTURE}/" DESTINATION "${WORK}")
endif()
execute_process(COMMAND "${PROGRAM}" WORKING_DIRECTORY "${WORK}" RESULT_VARIABLE status OUTPUT_VARIABLE out
                ERROR_VARIABLE err)
string(REPLACE "${WORK}/" "" out "${out}")
file(READ "${EXPECTED}" want)
if(NOT status STREQUAL "0")
  message(FATAL_ERROR "exit status ${status}\n--- stderr\n${err}")
endif()
if(NOT out STREQUAL want)
  message(FATAL_ERROR "printed\n${out}--- expected\n${want}--- stderr\n${err}")
endif()
