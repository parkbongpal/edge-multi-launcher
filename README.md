EXE 파일을 누르고 View raw를 누르면 exe파일만 다운로드됩니다.<br>
불안하면 코드 검사하고 직접 컴파일 명령어를 코드 파일가지고 컴파일하면됩니다.<br>
챗지피티한테 컴파일하는법 알려주면 잘알려주는데<br>
마지막 명령어만<br>
`bash
pyinstaller --noconsole --onefile --distpath . --name "EdgeMultiLauncher" main.py && rd /s /q build && del EdgeMultiLauncher.spec`<br>
이렇게 하면 자잘한 파일들 안남고 EXE파일만 남음.
