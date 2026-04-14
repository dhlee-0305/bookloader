# Bookloader

Bookloader는 엑셀로 관리하던 도서 목록과 독서 이력을 MySQL에 옮기는 적재 스크립트입니다.  
운영자가 수작업으로 정리해 둔 시트를 읽어 `books`, `reading_logs` 테이블에 반영하고, 비어 있는 도서 메타데이터는 카카오 도서 검색 API로 보강합니다.

## 서비스 개요

이 서비스는 "엑셀 기반 도서 관리"를 "서비스에서 조회 가능한 데이터"로 바꾸는 배치 도구입니다.

- 도서 목록 시트에서 책 제목, 저자, 출판사, 구입일, 상태를 읽어 `books` 테이블에 저장합니다.
- `isbn`, `coverUrl`이 비어 있으면 카카오 API로 검색해 값을 채웁니다.
- 보강된 `isbn`, `coverUrl`은 DB뿐 아니라 원본 엑셀에도 다시 기록합니다.
- 독서목록/보류목록 시트를 읽어 사용자별 독서 기록을 `reading_logs` 테이블에 저장합니다.
- 실행 로그는 콘솔과 `bookloader.log`에 함께 남깁니다.

## 처리 흐름

### 1. 도서 데이터 적재

설정 파일에 지정한 도서 시트(예: `도서목록`, `IT서적`)를 순서대로 읽습니다.

- 헤더는 각 시트의 2행을 사용합니다.
- 도서 상태는 엑셀 값 기준으로 서비스 상태값으로 변환됩니다.
  - `기부` -> `DONATED`
  - `판매` -> `SOLD`
  - 그 외 값 -> `OWNED`
- 동일 도서는 `INSERT IGNORE`로 중복 삽입을 방지합니다.
- `updatedAt`은 `purchaseDate`와 같은 값으로 저장됩니다.

### 2. 도서 메타데이터 보강

`isbn` 또는 `coverUrl`이 없는 행은 카카오 도서 검색 API를 호출해 보완합니다.

- 검색어는 `제목 + 저자 + 출판사` 조합으로 만듭니다.
- 검색 결과가 있으면 첫 번째 결과의 `isbn`, `thumbnail`을 사용합니다.
- 보강이 끝나면 엑셀 원본 파일의 해당 행에도 값을 다시 씁니다.

### 3. 독서 기록 적재

독서 관련 시트는 `books` 테이블의 제목 기준으로 책을 찾아 `reading_logs`를 생성합니다.

- `독서목록` 시트는 `년` 컬럼을 읽어 `createdAt`을 `YYYY-01-01`로 저장합니다.
- 연도 변환에 실패하면 `1999-01-01`을 기본값으로 사용합니다.
- `보류목록` 시트는 적재 시점의 현재 시간을 `createdAt`으로 사용합니다.
- 사용자 컬럼별로 개별 기록이 생성됩니다.
  - `대현` -> `dhlee.0305@gmail.com`
  - `문선` -> `yurina99@gmail.com`
- 시트별 상태값은 아래처럼 저장됩니다.
  - `독서목록` -> `READ`
  - `보류목록` -> `EXCLUDED`

## 사용 기술

| 기술 | 용도 |
|------|------|
| Python 3.11+ | 배치 스크립트 실행 |
| pandas | 엑셀 읽기 및 데이터 전처리 |
| openpyxl | 엑셀 파일 업데이트 |
| PyMySQL | MySQL 연결 및 INSERT 처리 |
| requests | 카카오 도서 검색 API 호출 |
| MySQL 8+ | 도서/독서 데이터 저장 |

## 실행 준비

### 1. 가상환경 생성

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 설정 파일 작성

`config.ini` 예시:

```ini
[database]
host = localhost
port = 3306
user = YOUR_DB_USER
password = YOUR_DB_PASSWORD
database = book_manager

[excel]
file_path = C:/path/to/Books.xlsx
sheets = 도서목록,IT서적

[reading_logs]
sheets = 독서목록,보류목록

[kakao]
rest_api_key = YOUR_KAKAO_REST_API_KEY
```

카카오 키는 `config.ini` 대신 환경변수 `KAKAO_REST_API_KEY`로도 설정할 수 있습니다.

## 엑셀 시트 규칙

모든 시트는 2행을 헤더로 사용합니다.

### 도서 시트 필수 컬럼

| 책 이름 | 작가 | 출판사 | 구입 날짜 | 상태 | isbn | coverUrl |
|---------|------|--------|-----------|------|------|------|

추가로 `isbn`, `coverUrl` 컬럼이 있으면 기존 값을 우선 사용하고, 비어 있으면 API로 보강합니다.

### 독서목록 시트 필수 컬럼

| 년 | 대현 | 문선 |
|----|------|------|

### 보류목록 시트 필수 컬럼

| 대현 | 문선 |
|------|------|

각 사용자 컬럼에는 해당 사용자가 읽은 책 제목을 입력합니다.

## 실행

```bash
python bookloader.py
```

실행이 끝나면 다음 결과를 확인할 수 있습니다.

- `books` 테이블 도서 적재 결과
- `reading_logs` 테이블 독서/보류 기록 적재 결과
- `bookloader.log` 실행 로그
- 엑셀 파일의 `isbn`, `coverUrl` 업데이트 결과
