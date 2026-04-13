import configparser
import os
import sys

import requests


def load_config(config_path: str = "config.ini") -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if not config.read(config_path, encoding="utf-8"):
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")
    return config


def get_api_key(config: configparser.ConfigParser) -> str:
    """config.ini 또는 환경변수에서 카카오 REST API 키를 읽어옵니다."""
    key = os.environ.get("KAKAO_REST_API_KEY")
    if key:
        return key

    try:
        key = config["kakao"]["rest_api_key"]
        if key and key != "YOUR_KAKAO_REST_API_KEY":
            return key
    except KeyError:
        pass

    raise ValueError(
        "카카오 REST API 키가 설정되지 않았습니다.\n"
        "config.ini의 [kakao] rest_api_key 또는 환경변수 KAKAO_REST_API_KEY를 설정해주세요."
    )


def search_book(
    config: configparser.ConfigParser,
    title: str = "",
    author: str = "",
    publisher: str = "",
) -> list[dict]:
    """
    카카오 도서 검색 API를 호출합니다.
    target 미지정 시 도서명·작가명·출판사명 전체를 대상으로 검색합니다.

    Args:
        config:    configparser 설정 객체
        title:     도서명
        author:    작가명
        publisher: 출판사명

    Returns:
        검색된 도서 정보 목록 (documents)
    """
    query = " ".join(p.strip() for p in (title, author, publisher) if p and p.strip())
    if not query:
        raise ValueError("title, author, publisher 중 하나 이상 입력해야 합니다.")

    api_key = get_api_key(config)
    url = "https://dapi.kakao.com/v3/search/book"
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {"query": query}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    return response.json().get("documents", [])


def print_book_info(book: dict, index: int) -> None:
    """도서 상세 정보를 출력합니다."""
    print(f"\n{'='*60}")
    print(f"[{index}] {book.get('title', '제목 없음')}")
    print(f"{'='*60}")
    print(f"  저자     : {', '.join(book.get('authors', []))}")

    translators = book.get("translators", [])
    if translators:
        print(f"  번역자   : {', '.join(translators)}")

    print(f"  출판사   : {book.get('publisher', '-')}")
    print(f"  출판일   : {book.get('datetime', '-')[:10]}")
    print(f"  ISBN     : {book.get('isbn', '-')}")
    print(f"  정가     : {book.get('price', 0):,}원")
    print(f"  판매가   : {book.get('sale_price', 0):,}원")
    print(f"  판매상태 : {book.get('status', '-')}")

    contents = book.get("contents", "")
    if contents:
        print(f"  소개     : {contents[:100]}{'...' if len(contents) > 100 else ''}")

    print(f"  상세URL  : {book.get('url', '-')}")


def main():
    config = load_config()

    print("검색어를 입력하세요. (하나 이상 필수, 나머지는 Enter로 건너뜀)")
    title     = input("  도서명   : ").strip()
    author    = input("  작가명   : ").strip()
    publisher = input("  출판사   : ").strip()

    if not any([title, author, publisher]):
        print("도서명, 작가명, 출판사 중 하나 이상 입력해야 합니다.")
        sys.exit(1)

    query = " ".join(p for p in [title, author, publisher] if p)
    print(f"\n검색어: '{query}'")
    books = search_book(config, title=title, author=author, publisher=publisher)

    if not books:
        print("검색 결과가 없습니다.")
        return

    print(f"총 {len(books)}건의 도서가 검색되었습니다.")
    for i, book in enumerate(books, start=1):
        print_book_info(book, i)


if __name__ == "__main__":
    main()
