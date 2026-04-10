import configparser
import logging
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pymysql

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bookloader.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── 도서 목록 설정 ────────────────────────────────────────────────
BOOK_COLUMN_MAP = {
    "책 이름": "title",
    "작가": "author",
    "출판사": "publisher",
    "구입 날짜": "purchaseDate",
    "상태": "status",
}

BOOK_STATUS_MAP = {
    "기부": "DONATED",
    "판매": "SOLD",
}

INSERT_BOOK_SQL = """
    INSERT IGNORE INTO books (title, author, publisher, purchaseDate, updatedAt, status)
    VALUES (%(title)s, %(author)s, %(publisher)s, %(purchaseDate)s, %(purchaseDate)s, %(status)s)
"""

# ── 독서 기록 설정 ────────────────────────────────────────────────
# 시트별 필수 컬럼 (보류목록은 '년' 미사용)
READING_LOG_COLUMNS = {
    "독서목록": ["년", "대현", "문선"],
    "보류목록": ["대현", "문선"],
}

USER_MAP = {
    "대현": "dhlee.0305@gmail.com",
    "문선": "yurina99@gmail.com",
}

# 시트명 → readStatus 매핑
READING_STATUS_MAP = {
    "독서목록": "READ",
    "보류목록": "EXCLUDED",
}

INSERT_READING_LOG_SQL = """
    INSERT INTO reading_logs (bookId, createdAt, updatedAt, userName, readStatus)
    VALUES (%(bookId)s, %(createdAt)s, %(updatedAt)s, %(userName)s, %(readStatus)s)
"""


# ── 공통 유틸 ──────────────────────────────────────────────────────
def load_config(config_path: str = "config.ini") -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if not config.read(config_path, encoding="utf-8"):
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")
    return config


def get_db_connection(config: configparser.ConfigParser) -> pymysql.connections.Connection:
    db_cfg = config["database"]
    return pymysql.connect(
        host=db_cfg["host"],
        port=int(db_cfg.get("port", 3306)),
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


# ── 도서 목록 처리 ────────────────────────────────────────────────
def read_book_sheet(file_path: str, sheet_name: str) -> pd.DataFrame:
    """도서 목록 시트 읽기 (헤더: 2행)"""
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=1, dtype=str)

    missing = [col for col in BOOK_COLUMN_MAP if col not in df.columns]
    if missing:
        raise ValueError(f"[{sheet_name}] 시트에 필수 컬럼이 없습니다: {missing}")

    df = df[list(BOOK_COLUMN_MAP.keys())].rename(columns=BOOK_COLUMN_MAP)
    df = df.dropna(how="all")
    df["purchaseDate"] = (
        df["purchaseDate"]
        .str.replace(r"\s+", "", regex=True)
        .str.replace(r"00$", "01", regex=True)
        .fillna("1999-01-01")
    )
    df["status"] = df["status"].map(BOOK_STATUS_MAP).fillna("OWNED")
    df = df.where(pd.notna(df), None)
    return df


def insert_books(cursor, df: pd.DataFrame) -> tuple[int, int]:
    inserted, skipped = 0, 0
    for _, row in df.iterrows():
        record = row.to_dict()
        cursor.execute(INSERT_BOOK_SQL, record)
        if cursor.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
            logger.debug("중복으로 건너뜀 - title: %s", record.get("title"))
    return inserted, skipped


def process_book_sheets(cursor, excel_path: str, sheet_names: list[str]):
    for sheet in sheet_names:
        logger.info("=== 도서 목록 시트 처리: [%s] ===", sheet)
        try:
            df = read_book_sheet(excel_path, sheet)
            logger.info("[%s] 읽은 행 수: %d", sheet, len(df))
            inserted, skipped = insert_books(cursor, df)
            logger.info("[%s] 저장 완료 - 삽입: %d건, 중복 무시: %d건", sheet, inserted, skipped)
        except ValueError as e:
            logger.error(e)
        except Exception as e:
            logger.error("[%s] 처리 중 오류 발생: %s", sheet, e)


# ── 독서 기록 처리 ────────────────────────────────────────────────
def load_books_cache(cursor) -> dict[str, int]:
    """books 테이블의 title → id 매핑을 캐시로 반환"""
    cursor.execute("SELECT id, title FROM books")
    cache = {row["title"]: row["id"] for row in cursor.fetchall() if row["title"]}
    logger.info("books 캐시 로드 완료: %d건", len(cache))
    return cache


def read_reading_sheet(file_path: str, sheet_name: str) -> pd.DataFrame:
    """독서/보류 목록 시트 읽기 (헤더: 2행)"""
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=1, dtype=str)

    required_cols = READING_LOG_COLUMNS[sheet_name]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"[{sheet_name}] 시트에 필수 컬럼이 없습니다: {missing}")

    df = df[required_cols].dropna(how="all")
    df = df.where(pd.notna(df), None)
    return df


def insert_reading_logs(cursor, df: pd.DataFrame, sheet_name: str, books_cache: dict[str, int]) -> tuple[int, int]:
    read_status = READING_STATUS_MAP[sheet_name]
    inserted, errors = 0, 0

    for _, row in df.iterrows():
        # createdAt 결정
        if sheet_name == "보류목록":
            # 보류목록: 현재 시간 사용
            created_at = datetime.now()
        else:
            # 독서목록: '년' 컬럼 → date(YYYY-01-01), 변환 불가 시 1999-01-01
            year_val = row.get("년")
            if year_val is None:
                continue
            try:
                created_at = date(int(float(year_val)), 1, 1)
            except (ValueError, TypeError):
                logger.warning(
                    "[%s] 년도 변환 불가 (값: '%s') - createdAt을 1999-01-01로 설정",
                    sheet_name, year_val,
                )
                created_at = date(1999, 1, 1)

        # 사용자별(대현, 문선) 처리
        for col_name, user_name in USER_MAP.items():
            title = row.get(col_name)
            if not title or str(title).strip().lower() == "nan":
                continue

            book_id = books_cache.get(title)
            if book_id is None:
                logger.error(
                    "[%s] books 테이블에서 도서를 찾을 수 없습니다 - title: '%s' (사용자: %s)",
                    sheet_name, title, user_name,
                )
                errors += 1
                continue

            cursor.execute(INSERT_READING_LOG_SQL, {
                "bookId": book_id,
                "createdAt": created_at,
                "updatedAt": datetime.now(),
                "userName": user_name,
                "readStatus": read_status,
            })
            inserted += 1

    return inserted, errors


def process_reading_log_sheets(cursor, excel_path: str, sheet_names: list[str], books_cache: dict[str, int]):
    for sheet in sheet_names:
        logger.info("=== 독서 기록 시트 처리: [%s] ===", sheet)
        try:
            df = read_reading_sheet(excel_path, sheet)
            logger.info("[%s] 읽은 행 수: %d", sheet, len(df))
            inserted, errors = insert_reading_logs(cursor, df, sheet, books_cache)
            logger.info("[%s] 저장 완료 - 삽입: %d건, 오류: %d건", sheet, inserted, errors)
        except ValueError as e:
            logger.error(e)
        except Exception as e:
            logger.error("[%s] 처리 중 오류 발생: %s", sheet, e)


# ── 메인 ──────────────────────────────────────────────────────────
def main():
    config = load_config()

    excel_path = config["excel"]["file_path"]
    if not Path(excel_path).exists():
        logger.error("엑셀 파일을 찾을 수 없습니다: %s", excel_path)
        sys.exit(1)

    book_sheets = [s.strip() for s in config["excel"]["sheets"].split(",")]
    reading_log_sheets = [s.strip() for s in config["reading_logs"]["sheets"].split(",")]

    conn = get_db_connection(config)
    try:
        with conn.cursor() as cursor:
            # 1단계: 도서 목록 저장
            process_book_sheets(cursor, excel_path, book_sheets)
            conn.commit()
            logger.info("도서 목록 저장 완료")

            # 2단계: books 캐시 로드 후 독서 기록 저장
            books_cache = load_books_cache(cursor)
            process_reading_log_sheets(cursor, excel_path, reading_log_sheets, books_cache)
            conn.commit()
            logger.info("독서 기록 저장 완료")

        logger.info("=== 전체 처리 완료 ===")

    except Exception as e:
        conn.rollback()
        logger.error("DB 오류로 롤백 처리: %s", e)
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
