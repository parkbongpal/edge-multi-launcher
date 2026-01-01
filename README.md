
<기능><br>
1. 드래그로 선택, 선택된 브라우저 실행 및 4X2로 배치하기<br>
(8개까지는 2번모니터에 4x2, 9,10번째브라우저는 1번모니터에 4x2 순환식배치)<br>
2. 이미 실행중인 브라우저가 다른 창에 가려져 백그라운드로 갈때 포그라운드로 가져오기<br>
3. 전체 최소화/전체 활성화<br>
4. 우클릭 및 드래그로 일괄종료<br>
5. 종료시 열린창 일괄종료<br>
6. 일괄 사이트 접속(현재탭에서 열기/새탭에서 열기)<br>
7. 새탭 열기,최근탭 닫기, 새로고침<br>
8. 텍스트 전송, 제어창 컴팩트,최적화<br>
9. F2로 단일 클릭 일괄전송

<img width="443" height="704" alt="image" src="https://github.com/user-attachments/assets/81e4c858-afd8-4c93-bd9f-2a9ecbbb7c21" />




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
이렇게 하면 자잘한 파일들 안남고 EXE파일만 남습니다.<br>
