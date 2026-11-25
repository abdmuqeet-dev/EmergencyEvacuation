@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" || exit /b 1
set "CM=C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake"
set "PATH=%CM%\CMake\bin;%CM%\Ninja;%PATH%"
cd /d D:\Projects\EmergencyEvacuation\third_party\VAL || exit /b 1
if exist build rmdir /s /q build
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 "-DCMAKE_CXX_FLAGS=/EHsc /D_HAS_AUTO_PTR_ETC=1 /FIfunctional /DYY_NO_UNISTD_H /w" -DCMAKE_INSTALL_PREFIX=D:\Projects\EmergencyEvacuation\third_party\VAL\install || exit /b 1
cmake --build build --config Release --target Validate2 || exit /b 1
echo BUILD_OK
