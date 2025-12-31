EXE 파일을 누르고 View raw를 누르면 exe파일만 다운로드됩니다.<br>
<br>
저는 모니터 2개를 상하로 쓰며 FHD모니터를 사용하고있으므로<br>
원본코드를 ai에게 자신의 모니터 상황에 맞게 바꿔달라고 하면됩니다.<br>
그 후에 직접 컴파일 명령어를 코드 파일가지고 컴파일하면됩니다.<br>
챗지피티한테 컴파일하는법 알려주면 잘알려주는데<br>
마지막 명령어만<br>
```bash
pyinstaller --noconsole --onefile --distpath . --name "EdgeMultiLauncher" main.py && rd /s /q build && del EdgeMultiLauncher.spec
```
<br>
이렇게 하면 자잘한 파일들 안남고 EXE파일만 남음.


