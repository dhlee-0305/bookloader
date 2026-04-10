# Bookloader

엑셀 파일에 정리된 도서 목록과 독서 기록을 MySQL 데이터베이스에 적재하는 Python 스크립트입니다.

## 서비스 설명

엑셀 파일의 시트별 데이터를 읽어 아래 두 단계로 DB에 저장합니다.

1. **도서 등록** (`books` 테이블)
   - 지정한 시트(예: `도서목록`, `IT서적`)에서 도서 정보를 읽어 저장합니다.
   - 중복 도서는 `INSERT IGNORE`로 자동 건너뜁니다.
   - `updatedAt`은 `purchaseDate`와 동일한 값으로 설정됩니다.

2. **독서 기록 등록** (`reading_logs` 테이블)
   - `독서목록` 시트: 연도(`년`) 컬럼을 기준으로 `createdAt`을 설정합니다.
   - `보류목록` 시트: `createdAt`을 현재 시간으로 설정합니다.
   - 사용자(`대현`, `문선`)별로 각각 레코드가 생성됩니다.

실행 결과는 콘솔과 `bookloader.log` 파일에 기록됩니다.

## 사용 기술

| 기술 | 버전 | 용도 |
|------|------|------|
| Python | 3.11+ | 런타임 |
| pandas | 2.0.0+ | 엑셀 파일 읽기 및 데이터 가공 |
| openpyxl | 3.1.0+ | pandas의 `.xlsx` 파일 엔진 |
| PyMySQL | 1.1.0+ | MySQL 연결 및 쿼리 실행 |
| MySQL | 8.0+ | 데이터 저장소 |

## 환경 셋팅 방법

### 1. Python 가상환경 생성 및 활성화

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. 의존성 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. config.ini 설정

프로젝트 루트에 `config.ini` 파일을 생성하고 아래 내용을 작성합니다.

```ini
[database]
host = localhost
port = 3306
user = YOUR_DB_USER
password = YOUR_DB_PASSWORD
database = book_manager

[excel]
file_path = /path/to/Books.xlsx
sheets = 도서목록,IT서적

[reading_logs]
sheets = 독서목록,보류목록
```

### 4. 엑셀 파일 형식

엑셀 파일의 각 시트는 **2행을 헤더**로 사용합니다.

**도서 목록 시트** (필수 컬럼)

| 책 이름 | 작가 | 출판사 | 구입 날짜 |
|---------|------|--------|-----------|

**독서목록 시트** (필수 컬럼)

| 년 | 대현 | 문선 |
|----|------|------|

**보류목록 시트** (필수 컬럼)

| 대현 | 문선 |
|------|------|

### 5. 실행

```bash
python bookloader.py
```
