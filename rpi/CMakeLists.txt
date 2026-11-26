cmake_minimum_required(VERSION 3.16)
project(RPiT3K LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(ALSA REQUIRED)
find_package(Threads REQUIRED)
set(NAM_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../NeuralAmpModelerCore" CACHE PATH "NAM Core checkout")
file(GLOB NAM_SOURCES "${NAM_ROOT}/NAM/*.cpp" "${NAM_ROOT}/NAM/*.c" "${NAM_ROOT}/NAM/*/*.cpp")
if(NOT EXISTS "${NAM_ROOT}/NAM/get_dsp.h")
  message(FATAL_ERROR "Clone NAM Core as described in rpi/README.md")
endif()
add_executable(rpit3k main.cpp ${NAM_SOURCES})
target_include_directories(rpit3k PRIVATE "${NAM_ROOT}" "${NAM_ROOT}/Dependencies/eigen" "${NAM_ROOT}/Dependencies/nlohmann" "${ALSA_INCLUDE_DIRS}")
target_compile_definitions(rpit3k PRIVATE NAM_SAMPLE_FLOAT NAM_ENABLE_A2_FAST)
target_compile_options(rpit3k PRIVATE $<$<CONFIG:Release>:-O3>)
set(RPIT3K_CPU "" CACHE STRING "Optional ARM64 CPU target; empty is portable")
if(RPIT3K_CPU AND CMAKE_SYSTEM_PROCESSOR MATCHES "^(aarch64|arm64)$")
  target_compile_options(rpit3k PRIVATE "-mcpu=${RPIT3K_CPU}")
endif()
target_link_libraries(rpit3k PRIVATE ${ALSA_LIBRARIES} Threads::Threads)

add_executable(rpit3k-dsp-test dsp_test.cpp)
target_compile_options(rpit3k-dsp-test PRIVATE $<$<CONFIG:Release>:-O3>)
enable_testing()
add_executable(rpit3k-metronome-test metronome_test.cpp)
add_test(NAME practice_metronome COMMAND rpit3k-metronome-test)
find_package(Python3 COMPONENTS Interpreter)
if(Python3_Interpreter_FOUND)
  add_test(NAME capture_calibration COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/calibration_test.py")
endif()
add_test(NAME native_dsp COMMAND rpit3k-dsp-test)
add_executable(rpit3k-live-rig-test live_rig_test.cpp)
target_link_libraries(rpit3k-live-rig-test PRIVATE Threads::Threads)
add_test(NAME live_rig_exchange COMMAND rpit3k-live-rig-test)

# Separate opt-in build of upstream default sample type and backend.
# No production A2-fast define or Cortex-A76 flags.
add_executable(nam-reference EXCLUDE_FROM_ALL nam_reference.cpp ${NAM_SOURCES})
target_include_directories(nam-reference PRIVATE "${NAM_ROOT}" "${NAM_ROOT}/Dependencies/eigen" "${NAM_ROOT}/Dependencies/nlohmann")
target_compile_options(nam-reference PRIVATE $<$<CONFIG:Release>:-O3>)

# Experimental TONE3000 Embedded 2.0.0 backend.
option(RPIT3K_EMBEDDED "Enable automatic Embedded A2 backend" ON)
if(RPIT3K_EMBEDDED)
  include(FetchContent)
  FetchContent_Declare(t3kembedded GIT_REPOSITORY https://github.com/tone-3000/embedded.git GIT_TAG v2.0.0 GIT_SHALLOW TRUE)
  FetchContent_GetProperties(t3kembedded)
  if(NOT t3kembedded_POPULATED)
    FetchContent_Populate(t3kembedded)
  endif()
  set(E76 "${t3kembedded_SOURCE_DIR}/engines/cortex-a76")
  target_sources(rpit3k PRIVATE "${E76}/a2lite/nam_a2lite.c" "${E76}/a2full/nam_a2full.c")
  target_include_directories(rpit3k PRIVATE "${E76}/a2lite" "${E76}/a2full")
  target_compile_definitions(rpit3k PRIVATE RPIT3K_EMBEDDED NAM_A2LITE_MAX_BUFFER_SIZE=64 NAM_A2FULL_MAX_BUFFER_SIZE=64 NAM_A2LITE_BLOCK_HINT=64 NAM_A2FULL_BLOCK_HINT=64)
endif()

# Upstream DaisySP-LGPL, built as a replaceable shared library.
set(DAISY_VENDOR "${CMAKE_CURRENT_SOURCE_DIR}/vendor/daisysp")
add_library(rpit3k-daisysp SHARED
  "${DAISY_VENDOR}/mit/Effects/chorus.cpp"
  "${DAISY_VENDOR}/lgpl/Source/Dynamics/compressor.cpp"
  "${DAISY_VENDOR}/lgpl/Source/Effects/reverbsc.cpp")
target_include_directories(rpit3k-daisysp PUBLIC
  "${DAISY_VENDOR}/mit"
  "${DAISY_VENDOR}/mit/Utility"
  "${DAISY_VENDOR}/lgpl/Source/Dynamics"
  "${DAISY_VENDOR}/lgpl/Source/Effects")
target_compile_options(rpit3k-daisysp PRIVATE $<$<CONFIG:Release>:-O3>)
target_link_libraries(rpit3k PRIVATE rpit3k-daisysp)
target_link_libraries(rpit3k-dsp-test PRIVATE rpit3k-daisysp)

add_executable(rpit3k-daisysp-characterization daisysp_test.cpp)
target_link_libraries(rpit3k-daisysp-characterization PRIVATE rpit3k-daisysp)
target_compile_options(rpit3k-daisysp-characterization PRIVATE $<$<CONFIG:Release>:-O3>)
add_test(NAME daisysp_characterization COMMAND rpit3k-daisysp-characterization)
set_tests_properties(daisysp_characterization PROPERTIES TIMEOUT 120)
if(Python3_Interpreter_FOUND)
  add_test(NAME tonecloud_session COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tonecloud_test.py")
endif()
