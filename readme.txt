python3 -m venv .venv
source .venv/bin/activate
pip install ccxt python-dotenv pandas
deactivate
rm -rf venv venv
sudo apt install unzip

1. 기본 명령어 (초기화 및 복제)
git init: 현재 폴더를 새로운 로컬 Git 저장소로 초기화.
git clone <url>: 원격 저장소를 로컬로 복제.2. 작업 및 스테이징 (로컬)
git status: 현재 파일들의 상태(변경된 파일, 스테이징 상태 등)를 확인.
git add <파일명>: 특정 파일을 스테이징 영역에 추가.
git add .: 변경된 모든 파일을 스테이징 영역에 추가.
git commit -m "메시지": 스테이징된 변경 사항을 버전으로 저장.3. 원격 저장소 연동 (GitHub 등)
git remote add origin <url>: 원격 저장소 주소를 'origin'으로 연결.
git push -u origin <branch>: 로컬 커밋을 원격 저장소에 반영.
git pull: 원격 저장소의 최신 변경 사항을 로컬로 가져와 병합.4. 브랜치 및 변경 사항 관리
git branch <브랜치명>: 브랜치 생성.
git checkout -b <브랜치명>: 브랜치 생성 후 이동.
git branch: 브랜치 목록 확인.git merge <브랜치명>: 현재 브랜치에 다른 브랜치 내용 병합.
git log: 커밋 히스토리 확인.5. 파일 복원 및 삭제
git restore <파일명>: 작업 디렉토리의 파일 변경 사항 취소 (2.23 이상).
git rm <파일명>: 파일을 삭제하고 스테이징 영역에 추가.

$ git remote -v
test    https://github.com/choiiis/balanchew.git (fetch)
test    https://github.com/choiiis/balanchew.git (push)

https://github.com/speed3651-hub/kiwoom